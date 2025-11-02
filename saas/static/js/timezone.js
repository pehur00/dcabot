/**
 * Automatic timezone conversion for UTC timestamps
 * Finds all elements with data-utc-time attribute and converts to user's local timezone
 */

document.addEventListener('DOMContentLoaded', function() {
    // Find all elements with UTC timestamps
    const timestampElements = document.querySelectorAll('[data-utc-time]');

    timestampElements.forEach(element => {
        const utcTimeStr = element.getAttribute('data-utc-time');
        if (!utcTimeStr || utcTimeStr === 'N/A' || utcTimeStr === 'Never') {
            return;
        }

        try {
            // Parse the UTC time
            const utcDate = new Date(utcTimeStr);

            // Check if date is valid
            if (isNaN(utcDate.getTime())) {
                console.warn('Invalid date:', utcTimeStr);
                return;
            }

            // Get format preference from data attribute
            const format = element.getAttribute('data-format') || 'datetime';

            let formattedTime;
            switch (format) {
                case 'date':
                    // Just the date (e.g., "Jan 15, 2025")
                    formattedTime = utcDate.toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                    });
                    break;

                case 'date-short':
                    // Short date (e.g., "Jan 15")
                    formattedTime = utcDate.toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric'
                    });
                    break;

                case 'datetime-short':
                    // Short datetime (e.g., "01/15 13:45:30")
                    formattedTime = utcDate.toLocaleString(undefined, {
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });
                    break;

                case 'time-only':
                    // Just time (e.g., "13:45:30")
                    formattedTime = utcDate.toLocaleTimeString(undefined, {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });
                    break;

                case 'datetime':
                default:
                    // Full datetime (e.g., "Jan 15, 2025 13:45:30")
                    formattedTime = utcDate.toLocaleString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });
                    break;
            }

            // Update the element's text content
            element.textContent = formattedTime;

            // Add title with full datetime for hover tooltip
            element.title = utcDate.toLocaleString(undefined, {
                dateStyle: 'full',
                timeStyle: 'long'
            });

        } catch (error) {
            console.error('Error converting timestamp:', utcTimeStr, error);
        }
    });
});
