"""
Weekly Export Sales Module
This module provides data collection, analysis, and reporting functionality
for USDA Weekly Export Sales data.
"""

from flask import Blueprint

# Create the blueprint
weekly_exports_bp = Blueprint(
    'weekly_exports',
    __name__,
    url_prefix='/weekly_exports',
    template_folder='templates',
    static_folder='static'
)

# Import routes to register them with the blueprint
# Use a try-except to handle different import contexts
try:
    from . import interactive_visual, report
except ImportError:
    # This happens when the file is executed directly instead of imported
    import interactive_visual
    import report

__version__ = '1.0.0'