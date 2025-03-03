# Weekly Export Sales Module

This module provides analysis and visualization of data from the USDA Export Sales Reporting (ESR) system. 

## Components

- **data_collector.py**: Collects data from the USDA ESR API and stores it in the SQLite database
- **data_analyzer.py**: Analyzes and processes the export sales data for visualization
- **report_generator.py**: Generates structured reports from the export sales data

## Database Structure

The module uses a SQLite database (`esr_data.db`) with the following tables:

- `metadata_commodities`: Information about available commodities
- `metadata_countries`: Information about countries in the dataset
- `metadata_units`: Units of measurement
- `metadata_regions`: Regional classifications
- `commodity_exports`: The main export sales data
- `data_releases`: Tracking information for data updates

## Usage

The module is designed to be used within the Market Research Platform but can also be used independently:

```python
from weekly_export_sales.data_analyzer import ExportAnalyzer
from weekly_export_sales.report_generator import WeeklyExportReportGenerator

# Initialize the analyzer with the database path
analyzer = ExportAnalyzer("path/to/esr_data.db")

# Get available commodities
commodities = analyzer.get_commodities()

# Load data for a specific commodity and time period
data = analyzer.load_data(commodity_code=101, start_my=2022, end_my=2023)

# Generate a report
report_generator = WeeklyExportReportGenerator("path/to/esr_data.db")
report = report_generator.generate_report(commodity_code=101)