Architecture
The Market Research Platform is built with a modular architecture allowing for easy expansion to new data sources:

Core Framework: Flask web application with organized blueprints for different data modules
Database: SQLite databases for each data module, with separate schemas for different data types
Data Collection: Automated data collection scripts for fetching and processing data from external APIs
Visualization Layer: Interactive front-end using Plotly.js for data visualization

Directory Structure
Copymarket_research_platform/
├── app.py                     # Main Flask application entry point
├── config.py                  # Configuration settings
├── modules/                   # Data source modules
│   ├── __init__.py            # Module registry
│   └── weekly_export_sales/   # Weekly Export Sales module
│       ├── __init__.py        # Blueprint definition
│       ├── data_load.py       # Data loading and processing
│       ├── interactive_visual.py  # Visualization routes
│       ├── report.py          # Report generation routes
│       ├── static/            # Module-specific static files
│       └── templates/         # Module-specific templates
├── static/                    # Global static files
├── templates/                 # Global templates
└── requirements.txt           # Python dependencies
