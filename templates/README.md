# HTML Templates Structure

This directory contains HTML templates for the Market Research Platform.

## Organization

- **base.html**: Base template with navigation, header, and footer
- **index.html**: Main dashboard/home page
- **weekly_export_sales/**: Templates for the Weekly Export Sales module
  - **weekly_exports.html**: Main visualization page with tabs
  - **export_report.html**: Report generation page

## Adding New Modules

When adding a new data source module to the platform:

1. Create a new subdirectory with the module name (e.g., `psd_data/`)
2. Add module-specific templates to this directory
3. Extend the base.html template in each new template

Example:
```html
{% extends "base.html" %}

{% block title %}Your Module Name - Market Research Platform{% endblock %}

{% block content %}
<!-- Your content here -->
{% endblock %}