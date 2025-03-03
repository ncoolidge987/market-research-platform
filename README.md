# Market Research Platform

A comprehensive web application that provides visualization and reporting tools for various data sources.

## Project Structure

market_research_platform/
│
├── app.py                       # Main Flask application
├── wsgi.py                      # WSGI entry point
│
├── weekly_export_sales/         # Weekly Export Sales module
│   ├── init.py              # Module initialization
│   ├── data_analyzer.py         # Analysis logic for visualization
│   ├── data_collector.py        # Data collection script
│   ├── report_generator.py      # Report generation module
│   ├── esr_data.db              # SQLite database
│   └── README.md                # Module documentation
│
├── templates/                   # HTML templates
│   ├── base.html                # Base template with navigation
│   ├── index.html               # Dashboard/home page
│   │
│   └── weekly_export_sales/     # Templates for Weekly Export Sales
│       ├── weekly_exports.html  # Main page with tabs
│       └── export_report.html   # Report page
│
└── static/                      # Static assets
├── css/
│   └── main.css             # Main stylesheet
└── js/
├── common.js            # Shared utility functions
└── weekly_export_sales/ # Weekly Export Sales JS
├── visualization.js # Visualization scripts
└── report.js        # Report generation scripts

## Features

- **Modular Design**: Each data source is implemented as a separate module with its own data collection, analysis, and reporting logic
- **Interactive Visualizations**: Dynamic data visualization with filtering, sorting, and customization options
- **Structured Reports**: Generate standardized reports similar to current PDF outputs
- **Responsive Interface**: Works on desktop and mobile devices

## Weekly Export Sales Module

This module provides visualization and reporting for data from the USDA Export Sales Reporting (ESR) system. Features include:

- Interactive visualization of weekly export data by commodity, country, and time period
- Multiple metrics for analysis (exports, sales, commitments)
- Various visualization types (weekly trends, country comparisons, marketing year comparisons)
- Structured reports with summary statistics and highlights