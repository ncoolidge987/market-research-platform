# This is the first script (paste.txt) that collects data
# Upload this file as data_collector.py

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='weekly_export_sales/data_collector.log'
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
    def __init__(self, api_keys: List[str], rate_limit_threshold: int = 50):
        self.api_keys = deque([APIKey(key) for key in api_keys])
        self.current_key = self.api_keys[0]
        self.base_url = "https://api.fas.usda.gov/api/esr"
        self.rate_limit_threshold = rate_limit_threshold
        self.retry_delay = 5
        
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
            proxies = {
                    'http': 'proxy.server:3128',
                    'https': 'proxy.server:3128'
                }
            response = requests.get(f"{self.base_url}/regions", headers=headers, timeout=30, proxies=proxies)
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
                proxies = {
                    'http': 'proxy.server:3128',
                    'https': 'proxy.server:3128'
                }
                response = requests.get(url, headers=self._get_headers(), timeout=120, proxies=proxies)
                
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

def main():
    api_keys = [
        "sXXbup7bXhySZZJBQv5VmmugtL3iW1UoRyjfeHJX",
        "O3NXAWRBr9DTb9EzpgzXcfB0FDhUWnyWSMZaT21u",
        "7eZV4w04Gpwd44zqOKoB92Is9nLwNdtTqqThNqPq",
        "P5cCtban45muGHzXVI9dgrdpnyCuQ1ogyJioOlgo",
        "H6UpwAmkElhx1Vjv3N3f0aBcBGND5KekrBTEXoFP"
    ]
    
    collector = ESRDataCollector(api_keys)
    
    try:
        conn = sqlite3.connect("weekly_export_sales/esr_data.db")
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

if __name__ == "__main__":
    main()