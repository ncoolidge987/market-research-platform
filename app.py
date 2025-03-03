"""
Market Research Platform - Main Flask Application
This is the entry point for the Market Research Platform, which integrates
multiple data sources and visualization modules.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import logging
import json
import pandas as pd
import plotly
import plotly.graph_objects as go

# Import data modules
from weekly_export_sales.data_analyzer import ExportAnalyzer
from weekly_export_sales.report_generator import WeeklyExportReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='app.log'
)

app = Flask(__name__)

# Database paths for each data source
ESR_DB_PATH = os.path.join(os.path.dirname(__file__), "weekly_export_sales/esr_data.db")

# Initialize analyzers for each data source
esr_analyzer = ExportAnalyzer(ESR_DB_PATH)
esr_report_generator = WeeklyExportReportGenerator(ESR_DB_PATH)

# Main dashboard route
@app.route('/')
def index():
    """Render the main dashboard/home page."""
    return render_template('index.html')

#############################
# Weekly Export Sales Routes
#############################

@app.route('/weekly_exports')
def weekly_exports():
    """Main page for Weekly Export Sales visualization and reports."""
    active_tab = request.args.get('tab', 'visualization')
    commodities = esr_analyzer.get_commodities().to_dict('records')

    return render_template(
        'weekly_export_sales/weekly_exports.html',
        active_tab=active_tab,
        commodities=commodities
    )

@app.route('/weekly_exports/report')
def export_report():
    """Dedicated route for Weekly Export Sales reports."""
    commodities = esr_analyzer.get_commodities().to_dict('records')
    return render_template(
        'weekly_export_sales/export_report.html',
        commodities=commodities
    )

# Weekly Export Sales API endpoints
@app.route('/weekly_exports/get_years', methods=['POST'])
def esr_get_years():
    """Get available marketing years for a selected commodity."""
    commodity_code = int(request.form.get('commodity_code'))
    try:
        years_df = esr_analyzer.get_marketing_year_info(commodity_code)
        years = sorted(years_df['marketYear'].tolist())
        return jsonify({
            'success': True,
            'years': years,
            'min_year': min(years),
            'max_year': max(years)
        })
    except Exception as e:
        logging.error(f"Error getting years: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/weekly_exports/get_countries', methods=['POST'])
def esr_get_countries():
    """Get countries with available data for selected commodity and years."""
    commodity_code = int(request.form.get('commodity_code'))
    start_year = int(request.form.get('start_year'))
    end_year = int(request.form.get('end_year'))

    try:
        countries = esr_analyzer.get_countries_with_data(commodity_code, start_year, end_year)
        return jsonify({
            'success': True,
            'countries': countries
        })
    except Exception as e:
        logging.error(f"Error getting countries: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/weekly_exports/get_plot', methods=['POST'])
def esr_get_plot():
    """Generate visualization based on user parameters."""
    commodity_code = int(request.form.get('commodity_code'))
    start_year = int(request.form.get('start_year'))
    end_year = int(request.form.get('end_year'))
    metric = request.form.get('metric')
    plot_type = request.form.get('plot_type')
    countries = request.form.getlist('countries[]')

    if 'All Countries' in countries:
        countries = ["All Countries"]

    try:
        # Load data
        data = esr_analyzer.load_data(commodity_code, start_year, end_year)

        if data.empty:
            return jsonify({
                'success': False,
                'error': 'No data available for the selected parameters'
            })

        # Get summary data
        summary = esr_analyzer.get_summary_data(data, metric, countries)

        # Create plot based on type
        if plot_type == 'weekly':
            plot_data = esr_analyzer.get_weekly_data(data, metric, countries)
            fig = create_weekly_plot(plot_data, metric, esr_analyzer.metrics[metric],
                                    summary['units'], start_year, end_year, countries)
        elif plot_type == 'country':
            plot_data = esr_analyzer.get_weekly_data_by_country(data, metric, countries)
            fig = create_country_plot(plot_data, metric, esr_analyzer.metrics[metric],
                                     summary['units'], start_year, end_year, countries)
        else:  # 'my_comparison'
            plot_data = esr_analyzer.get_marketing_year_data(data, metric, countries)
            fig = create_my_comparison_plot(plot_data, metric, esr_analyzer.metrics[metric],
                                          summary['units'], start_year, end_year, countries)

        # Convert plot to JSON
        plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        # Get commodity information
        commodity_info = esr_analyzer.unit_info

        return jsonify({
            'success': True,
            'plot': plot_json,
            'summary': summary,
            'commodity': {
                'name': commodity_info['commodity_name'],
                'unit': commodity_info['unit_name']
            }
        })
    except Exception as e:
        logging.error(f"Error generating plot: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/weekly_exports/generate_report', methods=['POST'])
def esr_generate_report():
    """Generate a structured report for Weekly Export Sales."""
    commodity_code = int(request.form.get('commodity_code'))
    report_type = request.form.get('report_type', 'weekly')

    try:
        report_data = esr_report_generator.generate_report(commodity_code, report_type)
        return jsonify({
            'success': True,
            'report': report_data
        })
    except Exception as e:
        logging.error(f"Error generating report: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

########################
# Plot Creation Functions
########################

def create_weekly_plot(data, metric, metric_name, units, start_year, end_year, countries):
    """Create a weekly trend plot."""
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    fig = go.Figure()
    for year in sorted(data['market_year'].unique()):
        year_data = data[data['market_year'] == year]
        fig.add_trace(go.Bar(
            x=year_data['weekEndingDate'],
            y=year_data[metric],
            name=f'MY {year-1}/{year}'
        ))

    title_suffix = ""
    if countries and "All Countries" not in countries:
        title_suffix = f" - {', '.join(countries) if len(countries) <= 3 else f'{len(countries)} Countries'}"

    fig.update_layout(
        title=f'{metric_name} - Weekly Trend (MY {start_year}-{end_year}){title_suffix}',
        xaxis_title='Week Ending Date',
        yaxis_title=units,
        showlegend=True,
        height=700,
        width=1000,
        template='plotly_white',
        barmode='overlay',
        legend=dict(
            x=1.05,
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255,255,255,0.5)',
            bordercolor='black',
            borderwidth=1,
            font=dict(size=10),
            traceorder='normal',
            itemsizing='constant',
            itemwidth=30,
            orientation='v',
            tracegroupgap=0
        ),
        margin=dict(l=50, r=150, t=100, b=50)
    )
    return fig

def create_country_plot(data, metric, metric_name, units, start_year, end_year, countries):
    """Create a plot showing data by country."""
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    fig = go.Figure()
    for country in sorted(data['countryName'].unique()):
        country_data = data[data['countryName'] == country]
        fig.add_trace(go.Bar(
            x=country_data['weekEndingDate'],
            y=country_data[metric],
            name=country
        ))

    title_suffix = ""
    if countries and "All Countries" not in countries:
        title_suffix = f" - {', '.join(countries) if len(countries) <= 3 else f'{len(countries)} Countries'}"

    fig.update_layout(
        title=f'{metric_name} - Weekly Trend by Country (MY {start_year}-{end_year}){title_suffix}',
        xaxis_title='Week Ending Date',
        yaxis_title=units,
        showlegend=True,
        height=700,
        width=1000,
        template='plotly_white',
        barmode='stack',
        legend=dict(
            x=1.05,
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255,255,255,0.5)',
            bordercolor='black',
            borderwidth=1,
            font=dict(size=10),
            traceorder='normal',
            itemsizing='constant',
            itemwidth=30,
            orientation='v',
            tracegroupgap=0
        ),
        margin=dict(l=50, r=150, t=100, b=50)
    )
    return fig

def create_my_comparison_plot(data, metric, metric_name, units, start_year, end_year, countries):
    """Create a marketing year comparison plot."""
    fig = go.Figure()

    if not data:
        fig.update_layout(title="No data available")
        return fig

    for year, year_data in data.items():
        df = year_data['data']
        start_date = year_data['start_date']

        start_date_str = start_date.strftime('%b %d') if start_date is not None else 'Unknown'

        fig.add_trace(go.Scatter(
            x=df['weeks_into_my'],
            y=df[metric],
            name=f'MY {year-1}/{year} (Start: {start_date_str})',
            mode='lines'
        ))

    title_suffix = ""
    if countries and "All Countries" not in countries:
        title_suffix = f" - {', '.join(countries) if len(countries) <= 3 else f'{len(countries)} Countries'}"

    fig.update_layout(
        title=f'Weekly {metric_name} - Marketing Year Comparison{title_suffix}',
        xaxis_title='Weeks into Marketing Year',
        yaxis_title=f'{units}',
        showlegend=True,
        height=700,
        width=1000,
        template='plotly_white',
        xaxis=dict(tickmode='linear', dtick=4),
        legend=dict(
            x=1.05,
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255,255,255,0.5)',
            bordercolor='black',
            borderwidth=1,
            font=dict(size=10),
            traceorder='normal',
            itemsizing='constant',
            itemwidth=30,
            orientation='v',
            tracegroupgap=0
        ),
        margin=dict(l=50, r=150, t=100, b=50)
    )
    return fig

if __name__ == '__main__':
    app.run(debug=True)