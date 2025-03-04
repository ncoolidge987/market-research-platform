/**
 * Weekly Export Sales Visualization JavaScript
 * Handles the interactive visualization functionality for the Weekly Export Sales module.
 */

$(document).ready(function() {
    // When commodity is selected, load years
    $('#commodity').change(function() {
        const commodityCode = $(this).val();
        if (commodityCode) {
            $.ajax({
                url: '/weekly_exports/get_years',
                type: 'POST',
                data: {
                    commodity_code: commodityCode
                },
                success: function(response) {
                    if (response.success) {
                        const years = response.years;

                        // Populate start year dropdown
                        let startYearOptions = '<option value="">Start Year</option>';
                        years.forEach(year => {
                            startYearOptions += `<option value="${year}">${year-1}/${year}</option>`;
                        });
                        $('#start-year').html(startYearOptions).prop('disabled', false);

                        // Populate end year dropdown
                        let endYearOptions = '<option value="">End Year</option>';
                        years.forEach(year => {
                            endYearOptions += `<option value="${year}">${year-1}/${year}</option>`;
                        });
                        $('#end-year').html(endYearOptions).prop('disabled', false);

                        // Set defaults to last 5 years
                        if (years.length > 0) {
                            const defaultStartIndex = Math.max(0, years.length - 5);
                            $('#start-year').val(years[defaultStartIndex]);
                            $('#end-year').val(years[years.length - 1]);

                            // Enable update countries button
                            $('#update-countries').prop('disabled', false);
                        }
                    } else {
                        alert('Error loading years: ' + response.error);
                    }
                },
                error: function() {
                    alert('Server error when loading years');
                }
            });
        } else {
            $('#start-year, #end-year').html('<option value="">Select Year</option>').prop('disabled', true);
            $('#update-countries').prop('disabled', true);
            $('#countries').html('<option value="All Countries" selected>All Countries</option>').prop('disabled', true);
            $('#update-plot').prop('disabled', true);
        }
    });

    // Update countries button
    $('#update-countries').click(function() {
        const commodityCode = $('#commodity').val();
        const startYear = $('#start-year').val();
        const endYear = $('#end-year').val();

        if (commodityCode && startYear && endYear) {
            showLoading('loading');

            $.ajax({
                url: '/weekly_exports/get_countries',
                type: 'POST',
                data: {
                    commodity_code: commodityCode,
                    start_year: startYear,
                    end_year: endYear
                },
                success: function(response) {
                    hideLoading('loading');

                    if (response.success) {
                        const countries = response.countries;

                        // Populate countries dropdown
                        let countryOptions = '<option value="All Countries">All Countries</option>';
                        countries.forEach(country => {
                            countryOptions += `<option value="${country}">${country}</option>`;
                        });

                        $('#countries').html(countryOptions).prop('disabled', false);
                        $('#update-plot').prop('disabled', false);
                    } else {
                        alert('Error loading countries: ' + response.error);
                    }
                },
                error: function() {
                    hideLoading('loading');
                    alert('Server error when loading countries');
                }
            });
        } else {
            alert('Please select a commodity and year range first');
        }
    });

    // Form submission
    $('#visualization-form').submit(function(e) {
        e.preventDefault();

        const commodityCode = $('#commodity').val();
        const startYear = $('#start-year').val();
        const endYear = $('#end-year').val();
        const countries = $('#countries').val() || ['All Countries'];
        const metric = $('#metric').val();
        const plotType = $('#plot-type').val();

        if (commodityCode && startYear && endYear && metric && plotType) {
            showLoading('loading');
            $('#plot-container').empty();
            $('#summary-container').hide();

            $.ajax({
                url: '/weekly_exports/get_plot',
                type: 'POST',
                data: {
                    commodity_code: commodityCode,
                    start_year: startYear,
                    end_year: endYear,
                    'countries[]': countries,
                    metric: metric,
                    plot_type: plotType
                },
                success: function(response) {
                    hideLoading('loading');

                    if (response.success) {
                        // Display the plot
                        const plotJson = JSON.parse(response.plot);
                        Plotly.newPlot('plot-container', plotJson.data, plotJson.layout);

                        // Update summary
                        const summary = response.summary;
                        const commodity = response.commodity;

                        let countryText = 'All Countries';
                        if (countries.length === 1 && countries[0] !== 'All Countries') {
                            countryText = countries[0];
                        } else if (countries.length > 1) {
                            countryText = `${countries.length} Selected Countries`;
                        }

                        const summaryHtml = `
                            <div class="row">
                                <div class="col-md-6">
                                    <p><strong>Commodity:</strong> ${commodity.name}</p>
                                    <p><strong>Countries:</strong> ${countryText}</p>
                                </div>
                                <div class="col-md-6">
                                    <p><strong>Latest Week:</strong> ${formatNumber(summary.latest_week)} ${summary.units}</p>
                                    <p><strong>Last Updated:</strong> ${formatDate(summary.latest_date)}</p>
                                </div>
                            </div>
                        `;

                        $('#summary-content').html(summaryHtml);
                        $('#summary-container').show();
                    } else {
                        $('#plot-container').html(`
                            <div class="alert alert-warning">
                                <h4>No Data Available</h4>
                                <p>${response.error}</p>
                                <p>Try changing your selection criteria.</p>
                            </div>
                        `);
                    }
                },
                error: function() {
                    hideLoading('loading');
                    showError('plot-container', 'An error occurred while generating the plot. Please try again later.');
                }
            });
        } else {
            alert('Please fill in all required fields');
        }
    });

    // Enable Update Plot button when years are selected
    $('#start-year, #end-year').change(function() {
        if ($('#commodity').val() && $('#start-year').val() && $('#end-year').val()) {
            $('#update-plot').prop('disabled', false);
            $('#update-countries').prop('disabled', false);
            $('#countries').prop('disabled', false);
        } else {
            $('#update-plot').prop('disabled', true);
        }
    });
    
    // Utility functions
    function formatNumber(num) {
        return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
    }

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