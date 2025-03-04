"""
Module registry for the Market Research Platform.
This file handles registration of all modules with the main Flask app.

Each module should:
1. Have its own config.py file with module-specific settings
2. Be independent from the global configuration
3. Create a Blueprint for registration
"""

def register_modules(app):
    """Register all modules with the Flask app."""
    # Import and register each module's blueprint
    from modules.weekly_export_sales import weekly_exports_bp
    app.register_blueprint(weekly_exports_bp)
    
    # Additional modules would be registered here
    # Example: from modules.another_module import another_module_bp
    #          app.register_blueprint(another_module_bp)