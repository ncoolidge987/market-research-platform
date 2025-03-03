# JavaScript Structure

This directory contains JavaScript files for the Market Research Platform.

## Organization

- **common.js**: Contains shared utilities and functions used across the platform
- **weekly_export_sales/**: JavaScript for the Weekly Export Sales module
  - **visualization.js**: Controls the interactive visualization functionality
  - **report.js**: Controls the report generation functionality

## Adding New Modules

When adding a new data source module to the platform:

1. Create a new subdirectory with the module name (e.g., `psd_data/`)
2. Add module-specific JavaScript files to this directory
3. Reference these files in the corresponding HTML templates

## Best Practices

- Use the common utilities from `common.js` where possible
- Keep module-specific code in the appropriate subdirectory
- Follow consistent naming conventions
- Add comments explaining the purpose of each function