/**
 * Weekly Export Sales Report JavaScript
 * Handles the report generation functionality for the Weekly Export Sales module.
 */

$(document).ready(function() {
    // Report form submission
    $('#report-form').submit(function(e) {
        e.preventDefault();
        
        const commodityCode = $('#report-commodity').val();
        const reportFormat = $('#report-format').val();
        const reportView = $('#report-view').val();
        
        if (!commodityCode) {
            alert('Please select a commodity');
            return;
        }
        
        // Show loading indicator
        showLoading('loading');
        
        // Make API request to generate report
        $.ajax({
            url: '/weekly_exports/generate_report',
            type: 'POST',
            data: {
                commodity_code: commodityCode,
                report_type: reportFormat,
                view_type: reportView
            },
            success: function(response) {
                hideLoading('loading');
                
                if (response.success) {
                    // Update report display with the returned data
                    const report = response.report;
                    
                    // Display commodity name and report date
                    if (report.commodity_info) {
                        $('#report-commodity-name').text(report.commodity_info.commodity_name);
                    }
                    
                    if (report.report_date) {
                        $('#report-week').text(formatDate(report.report_date));
                    } else {
                        // Use current date as fallback
                        $('#report-week').text(formatDate(new Date()));
                    }
                    
                    // Display placeholder or actual report
                    if (!report.data_available) {
                        // Show placeholder with message
                        $('#report-placeholder .alert-secondary').html(`
                            <p>${report.message || 'No data available for the selected report type.'}</p>
                            <p>This section will provide structured, printer-friendly reports that follow the format of current PDF exports.</p>
                        `);
                    }
                    
                    // Show the report container
                    $('#report-placeholder').show();
                    
                } else {
                    // Show error message
                    showError('report-container', 'Error generating report: ' + response.error);
                }
            },
            error: function() {
                hideLoading('loading');
                showError('report-container', 'Server error when generating report');
            }
        });
    });
    
    // Utility functions
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    function showLoading(elementId = 'loading') {
        const loadingElement = document.querySelector(`.${elementId}`);
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
    }

    function hideLoading(elementId = 'loading') {
        const loadingElement = document.querySelector(`.${elementId}`);
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }

    function showError(container, message) {
        const errorHtml = `
            <div class="alert alert-danger">
                <h4>Error</h4>
                <p>${message}</p>
            </div>
        `;

        document.getElementById(container).innerHTML = errorHtml;
    }
});