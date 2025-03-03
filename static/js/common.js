/**
 * Common JavaScript functions for the Market Research Platform
 * Contains shared utilities and functions used across multiple modules
 */

// Format numbers with commas for thousands separators
function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
}

// Format dates in a consistent way
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Show loading spinner
function showLoading(elementId = 'loading') {
    const loadingElement = document.querySelector(`.${elementId}`);
    if (loadingElement) {
        loadingElement.style.display = 'block';
    }
}

// Hide loading spinner
function hideLoading(elementId = 'loading') {
    const loadingElement = document.querySelector(`.${elementId}`);
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
}

// Show error message in a standardized format
function showError(container, message) {
    const errorHtml = `
        <div class="alert alert-danger">
            <h4>Error</h4>
            <p>${message}</p>
        </div>
    `;

    document.getElementById(container).innerHTML = errorHtml;
}

// Copy text to clipboard
function copyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
}

// Export functions for use in other modules
window.mrp = {
    formatNumber,
    formatDate,
    showLoading,
    hideLoading,
    showError,
    copyToClipboard
};