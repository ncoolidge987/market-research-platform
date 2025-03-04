"""
Data loading and database operations for the Weekly Export Sales module.
Handles fetching data from the USDA API and managing the local database.
"""

import requests
import pandas as pd
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from requests.exceptions import RequestException
from collections import deque
import logging
import sqlite3
import json
import os

# For direct execution, use absolute import
# When imported as part of package, use relative import
try:
    # Try relative import first (for when imported as part of package)
    from .config import WeeklyExportConfig
except ImportError:
    # Fall back to absolute import for direct script execution
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    from modules.weekly_export_sales.config import WeeklyExportConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=WeeklyExportConfig.DATA_LOG_PATH
)

@dataclass
class APIKey:
    key: str
    rate_limit_remaining: int = None
    last_used: float = 0
    
    def update_quota(self, remaining: int):
        self.rate_limit_remaining = remaining
        self.last_used = time.time()

class ESRDataCollector:
    def __init__(self, api_keys: List[str], rate_limit_threshold: int = WeeklyExportConfig.RATE_LIMIT_THRESHOLD):
        self.api_keys = deque([APIKey(key) for key in api_keys])
        self.current_key = self.api_keys[0]
        self.base_url = "https://api.fas.usda.gov/api/esr"
        self.rate_limit_threshold = rate_limit_threshold
        self.retry_delay = WeeklyExportConfig.RETRY_DELAY
        
    def _get_headers(self) -> Dict[str, str]:
        return {
            'X-Api-Key': self.current_key.key,
            "accept": "application/json"
        }
    
    def _rotate_api_key(self):
        initial_key = self.current_key
        while True:
            self.api_keys.rotate(-1)
            self.current_key = self.api_keys[0]
            
            if self.current_key == initial_key:
                logging.info("All API keys exhausted. Waiting for quota refresh...")
                time.sleep(300)
                self._check_all_quotas()
                continue
            
            if self.current_key.last_used < time.time() - 60:
                self._check_quota(self.current_key)
            
            if self.current_key.rate_limit_remaining is None or self.current_key.rate_limit_remaining >= self.rate_limit_threshold:
                break
    
    def _check_quota(self, api_key: APIKey) -> int:
        try:
            headers = {'X-Api-Key': api_key.key, "accept": "application/json"}
            response = requests.get(f"{self.base_url}/regions", headers=headers, timeout=30)
            response.raise_for_status()
            remaining = int(response.headers.get('X-Ratelimit-Remaining', 0))
            api_key.update_quota(remaining)
            return remaining
        except Exception:
            return 0
    
    def _check_all_quotas(self):
        for api_key in self.api_keys:
            self._check_quota(api_key)
    
    def _make_request(self, endpoint: str) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        retries = 0
        max_retries = 2
        backoff_factor = 1.5
        
        while retries < max_retries:
            try:
                logging.info(f"Request attempt {retries + 1}/{max_retries} to {url}")

                response = requests.get(url, headers=self._get_headers(), timeout=120)
                
                if response.status_code == 429:
                    self._rotate_api_key()
                    wait_time = self.retry_delay * (backoff_factor ** retries)
                    logging.info(f"Rate limit hit. Rotating API key and waiting {wait_time:.1f} seconds")
                    time.sleep(wait_time)
                    retries += 1
                    continue
                    
                response.raise_for_status()
                
                remaining = int(response.headers.get('X-Ratelimit-Remaining', 0))
                self.current_key.update_quota(remaining)
                
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    logging.warning(f"Invalid JSON response on attempt {retries + 1}")
                    retries += 1
                    time.sleep(self.retry_delay * (backoff_factor ** retries))
                    continue
                
                if data is None:
                    logging.warning(f"Null response on attempt {retries + 1}")
                    retries += 1
                    time.sleep(self.retry_delay * (backoff_factor ** retries))
                    continue
                
                if (isinstance(data, (list, dict)) and not data and 
                    not any(x in endpoint for x in ['/regions', '/countries', '/commodities'])):
                    logging.warning(f"Empty response on attempt {retries + 1}")
                    retries += 1
                    time.sleep(self.retry_delay * (backoff_factor ** retries))
                    continue
                
                if remaining < self.rate_limit_threshold:
                    self._rotate_api_key()
                
                return data
                
            except requests.exceptions.Timeout:
                wait_time = self.retry_delay * (backoff_factor ** retries)
                logging.warning(f"Request timeout on attempt {retries + 1}. Waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
                retries += 1
                
            except requests.exceptions.ConnectionError:
                wait_time = self.retry_delay * (backoff_factor ** retries)
                logging.warning(f"Connection error on attempt {retries + 1}. Waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
                retries += 1
                
            except requests.exceptions.RequestException as e:
                if retries < max_retries - 1:
                    wait_time = self.retry_delay * (backoff_factor ** retries)
                    logging.warning(f"Request failed on attempt {retries + 1}: {str(e)}. Waiting {wait_time:.1f} seconds")
                    time.sleep(wait_time)
                    retries += 1
                    continue
                logging.error(f"Request failed after {max_retries} attempts: {str(e)}")
                raise
                
        logging.error(f"Failed to get valid data from {url} after {max_retries} attempts")
        raise Exception(f"Maximum retries ({max_retries}) exceeded for {url}")

    def get_data(self, endpoint: str) -> pd.DataFrame:
        logging.info(f"Fetching data from {endpoint}...")
        data = self._make_request(endpoint)
        df = pd.DataFrame(data if data else [])
        if not df.empty:
            logging.info(f"Retrieved {len(df)} records with columns: {df.columns.tolist()}")
        return df
    
    def get_commodity_data(self, commodity_code: int, market_year: int) -> pd.DataFrame:
        endpoint = f"/exports/commodityCode/{commodity_code}/allCountries/marketYear/{market_year}"
        df = self.get_data(endpoint)
        if not df.empty:
            df['commodity_code'] = commodity_code
            df['market_year'] = market_year
        return df

def process_table_data(df: pd.DataFrame, table_name: str, conn: sqlite3.Connection):
    if df.empty:
        logging.info(f"No data to process for table {table_name}")
        return
        
    try:
        cursor = conn.cursor()
        current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Map pandas dtypes to SQLite types
        dtype_map = {
            'object': 'TEXT',
            'int64': 'INTEGER',
            'float64': 'REAL',
            'datetime64[ns]': 'TIMESTAMP',
            'bool': 'INTEGER'
        }
        
        # Create table if it doesn't exist
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            columns = [f"{col} {dtype_map.get(str(dtype), 'TEXT')}" 
                      for col, dtype in df.dtypes.items()]
            columns.append("updated_at TIMESTAMP")
            
            create_table_sql = f"""
            CREATE TABLE {table_name} (
                {', '.join(columns)}
            )
            """
            logging.info(f"Creating table: {create_table_sql}")
            cursor.execute(create_table_sql)
        
        # Get existing columns and add any new ones
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        for col in df.columns:
            if col not in existing_columns and col != 'updated_at':
                sql_type = dtype_map.get(str(df[col].dtype), 'TEXT')
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type}"
                logging.info(f"Adding new column: {alter_sql}")
                cursor.execute(alter_sql)

        # For commodity_exports: Handle duplicates and update data
        if table_name == 'commodity_exports':
            if 'commodity_code' in df.columns and 'market_year' in df.columns:
                commodity_years = df[['commodity_code', 'market_year']].drop_duplicates().values
                for commodity_code, market_year in commodity_years:
                    # First, check for duplicates in the new data
                    duplicate_check = df[(df['commodity_code'] == commodity_code) & 
                                        (df['market_year'] == market_year)]
                    
                    if duplicate_check.duplicated(['weekEndingDate', 'countryCode']).any():
                        # Keep only the last (newest) occurrence of each duplicate
                        logging.warning(f"Found duplicates in import data for commodity {commodity_code}, year {market_year}")
                        # Sort by weekEndingDate to ensure we're keeping the newest
                        # Since API data might not have a timestamp, weekEndingDate is the best proxy for recency
                        sorted_df = df.sort_values('weekEndingDate', ascending=True)  # Sort so newest is last
                        df = sorted_df.drop_duplicates(['commodity_code', 'market_year', 'weekEndingDate', 'countryCode'], keep='last')
                    
                    # Now delete existing records
                    cursor.execute("""
                        DELETE FROM commodity_exports 
                        WHERE commodity_code = ? AND market_year = ?
                    """, (commodity_code, market_year))
                    logging.info(f"Deleted existing records for commodity {commodity_code}, year {market_year}")
        
        # For metadata tables: Drop and recreate
        elif table_name.startswith('metadata_'):
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            columns = [f"{col} {dtype_map.get(str(dtype), 'TEXT')}" 
                      for col, dtype in df.dtypes.items()]
            columns.append("updated_at TIMESTAMP")
            
            create_table_sql = f"""
            CREATE TABLE {table_name} (
                {', '.join(columns)}
            )
            """
            cursor.execute(create_table_sql)
        
        # Insert new data
        insert_df = df.copy()
        insert_df['updated_at'] = current_timestamp
        insert_df.to_sql(table_name, conn, if_exists='append', index=False)
        
        conn.commit()
        logging.info(f"Processed {len(df)} records for table {table_name}")
        
    except Exception as e:
        logging.error(f"Error processing data for table {table_name}: {str(e)}")
        raise

class ExportDataManager:
    """Data manager class for export sales data handling database operations."""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or WeeklyExportConfig.DB_PATH
        self._ensure_db_directory()
        self.metrics = {
            'weeklyExports': 'Weekly Exports',
            'accumulatedExports': 'Accumulated Exports',
            'outstandingSales': 'Outstanding Sales',
            'grossNewSales': 'Gross New Sales',
            'netSales': 'Net Sales',
            'totalCommitment': 'Total Commitment'
        }
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def get_commodities(self) -> pd.DataFrame:
        """Get all available commodities."""
        with self.get_connection() as conn:
            return pd.read_sql("""
                SELECT commodityCode, commodityName
                FROM metadata_commodities
                ORDER BY commodityName
            """, conn)

    def get_countries(self) -> pd.DataFrame:
        """Get all available countries."""
        with self.get_connection() as conn:
            return pd.read_sql("""
                SELECT DISTINCT countryCode, countryName
                FROM metadata_countries
                ORDER BY countryName
            """, conn)

    def get_countries_with_data(self, commodity_code: int, start_my: int, end_my: int) -> List[str]:
        """Get countries that have data for the selected commodity and marketing years."""
        with self.get_connection() as conn:
            df = pd.read_sql("""
                SELECT
                    mc.countryName,
                    SUM(COALESCE(e.weeklyExports, 0)) as total_exports
                FROM commodity_exports e
                JOIN metadata_countries mc ON e.countryCode = mc.countryCode
                WHERE e.commodityCode = ?
                AND e.market_year BETWEEN ? AND ?
                GROUP BY mc.countryName
                ORDER BY total_exports DESC
            """, conn, params=(commodity_code, start_my, end_my))

            return df['countryName'].tolist()
            
    def get_marketing_year_info(self, commodity_code: int) -> pd.DataFrame:
        """Get marketing year information for a commodity."""
        with self.get_connection() as conn:
            my_dates = pd.read_sql("""
                SELECT
                    marketYear,
                    marketYearStart,
                    marketYearEnd
                FROM data_releases
                WHERE commodityCode = ?
                ORDER BY marketYear
            """, conn, params=(commodity_code,))

            if my_dates.empty:
                raise ValueError(f"No marketing year data for commodity {commodity_code}")

            my_dates['marketYearStart'] = pd.to_datetime(my_dates['marketYearStart'])
            my_dates['marketYearEnd'] = pd.to_datetime(my_dates['marketYearEnd'])

            latest_year = my_dates['marketYear'].max()
            latest_year_data = my_dates[my_dates['marketYear'] == latest_year].iloc[0]

            next_year_data = pd.DataFrame({
                'marketYear': [latest_year + 1],
                'marketYearStart': [latest_year_data['marketYearStart'] + pd.offsets.DateOffset(years=1)],
                'marketYearEnd': [latest_year_data['marketYearEnd'] + pd.offsets.DateOffset(years=1)]
            })

            return pd.concat([my_dates, next_year_data], ignore_index=True)
            
    def get_unit_info(self, commodity_code: int) -> dict:
        """Get unit information for a commodity."""
        with self.get_connection() as conn:
            info = pd.read_sql("""
                SELECT
                    m.commodityCode,
                    m.commodityName,
                    m.unitId,
                    u.unitNames
                FROM metadata_commodities m
                JOIN metadata_units u ON m.unitId = u.unitId
                WHERE m.commodityCode = ?
            """, conn, params=(commodity_code,))

            if info.empty:
                raise ValueError(f"No commodity found with code {commodity_code}")

            return {
                'commodity_code': info['commodityCode'].iloc[0],
                'commodity_name': info['commodityName'].iloc[0],
                'unit_id': info['unitId'].iloc[0],
                'unit_name': info['unitNames'].iloc[0]
            }

    def load_data(self, commodity_code: int, start_my: int, end_my: int) -> pd.DataFrame:
        """Load export data for a commodity and time period."""
        my_dates = self.get_marketing_year_info(commodity_code)
        unit_info = self.get_unit_info(commodity_code)
        
        # Validate marketing years
        if start_my > end_my:
            raise ValueError("Start marketing year must be <= end marketing year")
        if not all(my in my_dates['marketYear'].values for my in range(start_my, end_my + 1)):
            raise ValueError("Some specified marketing years not found in database")
        
        with self.get_connection() as conn:
            exports_df = pd.read_sql("""
                SELECT
                    e.*,
                    c.commodityName,
                    mc.countryName,
                    mc.countryDescription,
                    mc.regionId,
                    u.unitNames as unit
                FROM commodity_exports e
                JOIN metadata_commodities c ON e.commodityCode = c.commodityCode
                JOIN metadata_countries mc ON e.countryCode = mc.countryCode
                JOIN metadata_units u ON e.unitId = u.unitId
                WHERE e.commodityCode = ?
                AND e.market_year BETWEEN ? AND ?
                ORDER BY weekEndingDate
            """, conn, params=(commodity_code, start_my, end_my))

        if exports_df.empty:
            logging.warning(f"No export data for commodity {commodity_code} in years {start_my}-{end_my}")
            return pd.DataFrame()

        exports_df['weekEndingDate'] = pd.to_datetime(exports_df['weekEndingDate'])

        column_mappings = {
            'current': {
                'netSales': 'currentMYNetSales',
                'totalCommitment': 'currentMYTotalCommitment',
                'outstandingSales': 'outstandingSales',
                'accumulatedExports': 'accumulatedExports',
                'weeklyExports': 'weeklyExports',
                'grossNewSales': 'grossNewSales'
            },
            'next': {
                'netSales': 'nextMYNetSales',
                'outstandingSales': 'nextMYOutstandingSales',
            }
        }

        # Make a temporary copy to pre-calculate week numbers for marketing year transitions
        temp_df = exports_df.copy()

        # Join with marketing year dates
        temp_df = temp_df.merge(my_dates, left_on='market_year', right_on='marketYear', how='left')

        # Calculate weeks into marketing year (to identify week 1)
        temp_df['weeks_into_my'] = temp_df.apply(
            lambda row: ((row['weekEndingDate'] - row['marketYearStart']).days // 7 + 1)
            if pd.notna(row['weekEndingDate']) and pd.notna(row['marketYearStart']) else None,
            axis=1
        )

        # Process current marketing year data
        current_my_data = exports_df.drop(columns=list(column_mappings['next'].values()), errors='ignore')
        for std_col, source_col in column_mappings['current'].items():
            if source_col in current_my_data.columns and std_col != source_col:
                current_my_data[std_col] = current_my_data[source_col]
        current_my_data = current_my_data.drop(columns=[col for std_col, col in column_mappings['current'].items()
                                            if std_col != col and col in current_my_data.columns],
                                            errors='ignore')

        # Process next marketing year data
        next_my_data = exports_df.copy()

        # Join next_my_data with temp_df to get the weeks_into_my column
        next_my_data = next_my_data.merge(
            temp_df[['weekEndingDate', 'market_year', 'countryCode', 'weeks_into_my']],
            on=['weekEndingDate', 'market_year', 'countryCode'],
            how='left'
        )

        # For week 1 data, only keep rows that have meaningful next MY data
        week_one_data = next_my_data[next_my_data['weeks_into_my'] == 1]
        other_weeks_data = next_my_data[next_my_data['weeks_into_my'] != 1]

        # For week 1, we'll be selective about which data to keep
        filtered_week_one = week_one_data.copy()
        for _, source_col in column_mappings['next'].items():
            if source_col in filtered_week_one.columns:
                # Keep rows where next MY data is meaningful (not null and not zero)
                mask = pd.notna(filtered_week_one[source_col]) & (filtered_week_one[source_col] != 0)
                filtered_week_one = filtered_week_one[mask]

        # Recombine with other weeks data
        next_my_data = pd.concat([filtered_week_one, other_weeks_data], ignore_index=True)

        # Drop the current marketing year columns and weeks_into_my
        next_my_data = next_my_data.drop(columns=['weeks_into_my'] +
                                        [col for col in list(column_mappings['current'].values())
                                        if col in next_my_data.columns],
                                        errors='ignore')

        # Continue with normal processing for next MY data
        for std_col, source_col in column_mappings['next'].items():
            if source_col in next_my_data.columns and std_col != source_col:
                next_my_data[std_col] = next_my_data[source_col]

        next_my_data = next_my_data.drop(columns=[col for std_col, col in column_mappings['next'].items()
                                        if std_col != col and col in next_my_data.columns],
                                        errors='ignore')

        # Adjust the marketing year for next MY data
        next_my_data['market_year'] = next_my_data['market_year'] + 1

        # Combine current and next MY data
        processed_data = pd.concat([current_my_data, next_my_data], ignore_index=True)

        # Ensure no duplicates in the final dataset
        processed_data = processed_data.drop_duplicates(['weekEndingDate', 'market_year', 'countryCode'], keep='first')

        # Convert numeric columns
        numeric_columns = list(self.metrics.keys())
        for col in numeric_columns:
            if col in processed_data.columns:
                processed_data[col] = pd.to_numeric(processed_data[col], errors='coerce')

        processed_data['display_units'] = unit_info['unit_name']
        processed_data = processed_data.merge(my_dates, left_on='market_year', right_on='marketYear', how='left')

        processed_data['weeks_into_my'] = processed_data.apply(
            lambda row: ((row['weekEndingDate'] - row['marketYearStart']).days // 7 + 1)
            if pd.notna(row['weekEndingDate']) and pd.notna(row['marketYearStart']) else None,
            axis=1
        )

        processed_data = processed_data.sort_values('weekEndingDate').reset_index(drop=True)
        logging.info(f"Loaded {len(processed_data)} records for commodity {commodity_code}")
        return processed_data
        
    def get_summary_data(self, df: pd.DataFrame, metric: str, countries: List[str] = None) -> Dict:
        """Get summary statistics for the specified metric and countries."""
        if df.empty:
            return {
                'latest_week': 0,
                'units': 'N/A',
                'latest_date': 'N/A'
            }

        if countries and "All Countries" not in countries:
            filtered_df = df[df['countryName'].isin(countries)]
        else:
            filtered_df = df

        if filtered_df.empty:
            return {
                'latest_week': 0,
                'units': df['display_units'].iloc[0] if not df.empty else 'N/A',
                'latest_date': 'N/A'
            }

        latest_date = filtered_df['weekEndingDate'].max()
        latest_week_df = filtered_df[filtered_df['weekEndingDate'] == latest_date]

        # Get values and convert NumPy types to Python native types
        latest_week = float(latest_week_df[metric].sum()) if metric in latest_week_df.columns else 0

        return {
            'latest_week': latest_week,
            'units': filtered_df['display_units'].iloc[0],
            'latest_date': latest_date.strftime('%Y-%m-%d') if not pd.isna(latest_date) else 'N/A'
        }
        
    def get_weekly_data(self, df: pd.DataFrame, metric: str, countries: List[str] = None) -> pd.DataFrame:
        """Get weekly aggregated data for plotting."""
        if df.empty:
            return pd.DataFrame()

        if countries and "All Countries" not in countries:
            filtered_df = df[df['countryName'].isin(countries)]
        else:
            filtered_df = df

        if filtered_df.empty:
            return pd.DataFrame()

        weekly_data = filtered_df.groupby(['market_year', 'weekEndingDate'])[metric].sum().reset_index()
        return weekly_data
        
    def get_weekly_data_by_country(self, df: pd.DataFrame, metric: str, countries: List[str] = None) -> pd.DataFrame:
        """Get weekly data by country for plotting."""
        if df.empty:
            return pd.DataFrame()

        if countries and "All Countries" not in countries:
            filtered_df = df[df['countryName'].isin(countries)]
        else:
            filtered_df = df

        if filtered_df.empty:
            return pd.DataFrame()

        weekly_data = filtered_df.groupby(['market_year', 'weekEndingDate', 'countryName'])[metric].sum().reset_index()
        return weekly_data
        
    def get_marketing_year_data(self, df: pd.DataFrame, metric: str, countries: List[str] = None, 
                               start_my: int = None, end_my: int = None) -> Dict[int, pd.DataFrame]:
        """Get data organized by weeks into marketing year for comparison."""
        if df.empty:
            return {}

        if countries and "All Countries" not in countries:
            filtered_df = df[df['countryName'].isin(countries)]
        else:
            filtered_df = df

        if filtered_df.empty:
            return {}
            
        if start_my is None or end_my is None:
            # Find min and max years in the dataframe
            start_my = filtered_df['market_year'].min()
            end_my = filtered_df['market_year'].max()

        result = {}
        max_weeks = 0

        for year in range(start_my, end_my + 1):
            year_data = filtered_df[filtered_df['market_year'] == year].copy()
            if not year_data.empty and 'weeks_into_my' in year_data.columns:
                year_data_grouped = year_data.groupby(['weeks_into_my'])[metric].sum().reset_index()

                if not year_data_grouped.empty:
                    max_weeks = max(max_weeks, int(year_data_grouped['weeks_into_my'].max()))
                    min_weeks = min(1, int(year_data_grouped['weeks_into_my'].min()))
                    all_weeks = pd.DataFrame({'weeks_into_my': range(min_weeks, max_weeks + 1)})
                    year_data_complete = pd.merge(all_weeks, year_data_grouped, on='weeks_into_my', how='left')

                    result[year] = {
                        'data': year_data_complete,
                        'start_date': year_data['marketYearStart'].iloc[0] if not year_data['marketYearStart'].isna().all() else None
                    }

        return result


def collect_data():
    """Run the data collection process."""
    # Ensure data directories exist
    WeeklyExportConfig.ensure_directories()
    
    collector = ESRDataCollector(WeeklyExportConfig.API_KEYS)
    
    try:
        conn = sqlite3.connect(WeeklyExportConfig.DB_PATH)
        cursor = conn.cursor()
        
        # Create releases tracking table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_releases (
            commodityCode INTEGER,
            marketYear INTEGER,
            releaseTimeStamp TEXT,
            recorded_at TIMESTAMP,
            marketYearStart TEXT,
            marketYearEnd TEXT,
            PRIMARY KEY (commodityCode, marketYear)
        )
        """)
        
        # Update metadata
        logging.info("Updating metadata tables")
        metadata_endpoints = {
            'regions': '/regions',
            'units': '/unitsOfMeasure',
            'commodities': '/commodities',
            'countries': '/countries'
        }
        
        for name, endpoint in metadata_endpoints.items():
            df = collector.get_data(endpoint)
            if df.empty:
                raise Exception(f"Failed to fetch {name} data")
            process_table_data(df, f"metadata_{name}", conn)
        
        # Get current releases
        releases_df = collector.get_data('/datareleasedates')
        if releases_df.empty:
            raise Exception("Failed to fetch release dates")
            
        # Get existing release records
        cursor.execute("SELECT commodityCode, marketYear, releaseTimeStamp FROM data_releases")
        existing_releases = {(row[0], row[1]): row[2] for row in cursor.fetchall()}
        
        # Find records that need updating
        updates_needed = []
        for _, row in releases_df.iterrows():
            commodity_code = row['commodityCode']
            market_year = row['marketYear']
            release_timestamp = row['releaseTimeStamp']
            
            last_release = existing_releases.get((commodity_code, market_year))
            if not last_release or release_timestamp > last_release:
                updates_needed.append((commodity_code, market_year))
                
        logging.info(f"Found {len(updates_needed)} records requiring updates")
        
        # Process updates
        for commodity_code, market_year in updates_needed:
            try:
                logging.info(f"Fetching data for commodity {commodity_code}, year {market_year}")
                export_data = collector.get_commodity_data(commodity_code, market_year)
                
                if not export_data.empty:
                    process_table_data(export_data, 'commodity_exports', conn)
                    
                    # Update release timestamp
                    release_info = releases_df[
                        (releases_df['commodityCode'] == commodity_code) & 
                        (releases_df['marketYear'] == market_year)
                    ].iloc[0]
                    
                    cursor.execute("""
                    INSERT OR REPLACE INTO data_releases 
                    (commodityCode, marketYear, releaseTimeStamp, recorded_at, marketYearStart, marketYearEnd)
                    VALUES (?, ?, ?, datetime('now'), ?, ?)
                    """, (
                        commodity_code, 
                        market_year, 
                        release_info['releaseTimeStamp'],
                        release_info.get('marketYearStart'),
                        release_info.get('marketYearEnd')
                    ))
                    
                conn.commit()
                
            except Exception as e:
                logging.error(f"Error processing commodity {commodity_code}, year {market_year}: {str(e)}")
                continue
            
    except Exception as e:
        logging.error(f"Error in main execution: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

# If run directly, collect data
if __name__ == "__main__":
    collect_data()