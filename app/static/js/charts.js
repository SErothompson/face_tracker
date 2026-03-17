/**
 * Dashboard Charts - Line and Radar chart rendering using Chart.js
 */

let trendsChart = null;
let radarChart = null;

/**
 * Initialize and render the trends line chart
 */
async function initTrendsChart() {
    const canvas = document.getElementById("trendsChart");
    if (!canvas) return;

    try {
        const response = await fetch("/api/trends");
        const data = await response.json();

        if (!data || data.length === 0) {
            canvas.parentElement.innerHTML = '<div class="alert alert-info">No analysis data yet. Upload a session and run analysis to see trends.</div>';
            return;
        }

        // Format data for Chart.js
        const labels = data.map(d => formatDateShort(d.date));
        const scores = data.map(d => d.overall_score);

        // Destroy existing chart if it exists
        if (trendsChart) {
            trendsChart.destroy();
        }

        trendsChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Overall Health Score',
                    data: scores,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    pointBackgroundColor: '#0d6efd',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: {size: 14},
                        bodyFont: {size: 13},
                        displayColors: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        min: 0,
                        ticks: {
                            callback: function(value) {
                                return value;
                            }
                        },
                        title: {
                            display: true,
                            text: 'Score (0-100)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Session Date'
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error("Error loading trends chart:", error);
        canvas.parentElement.innerHTML = '<div class="alert alert-danger">Error loading trends data.</div>';
    }
}

/**
 * Initialize and render the latest session radar chart
 */
async function initRadarChart() {
    const canvas = document.getElementById("radarChart");
    if (!canvas) return;

    try {
        // Get the latest session ID from data attribute
        const latestSessionId = canvas.dataset.sessionId;

        if (!latestSessionId) {
            canvas.parentElement.innerHTML = '<div class="alert alert-info">No analysis data yet. Upload a session and run analysis to see condition breakdown.</div>';
            return;
        }

        const response = await fetch(`/api/session/${latestSessionId}/breakdown`);

        if (!response.ok) {
            canvas.parentElement.innerHTML = '<div class="alert alert-info">No analysis data for this session.</div>';
            return;
        }

        const data = await response.json();

        if (!data.conditions) {
            canvas.parentElement.innerHTML = '<div class="alert alert-info">No condition data available.</div>';
            return;
        }

        // Extract condition names and scores
        const conditionNames = [
            'acne',
            'texture',
            'dark_spots',
            'wrinkles',
            'under_eye',
            'redness'
        ];

        const labels = conditionNames.map(name => formatConditionName(name));
        const scores = conditionNames.map(name => {
            const condition = data.conditions[name];
            return condition ? condition.score : 0;
        });

        // Destroy existing chart if it exists
        if (radarChart) {
            radarChart.destroy();
        }

        radarChart = new Chart(canvas, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Condition Scores',
                    data: scores,
                    borderColor: '#198754',
                    backgroundColor: 'rgba(25, 135, 84, 0.1)',
                    borderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    pointBackgroundColor: '#198754',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        callbacks: {
                            label: function(context) {
                                return context.label + ': ' + Math.round(context.parsed.r) + '/100';
                            }
                        }
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        min: 0,
                        ticks: {
                            stepSize: 20
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error("Error loading radar chart:", error);
        canvas.parentElement.innerHTML = '<div class="alert alert-danger">Error loading condition data.</div>';
    }
}

/**
 * Load and display summary stats
 */
async function loadSummaryStats() {
    try {
        const response = await fetch("/api/sessions/summary");
        const data = await response.json();

        // Update stat cards
        const totalSessionsEl = document.getElementById("totalSessions");
        const avgScoreEl = document.getElementById("avgScore");
        const bestScoreEl = document.getElementById("bestScore");
        const worstScoreEl = document.getElementById("worstScore");

        if (totalSessionsEl) totalSessionsEl.textContent = data.total_sessions || 0;
        if (avgScoreEl) avgScoreEl.textContent = data.avg_score || 0;
        if (bestScoreEl) bestScoreEl.textContent = data.best_score || 0;
        if (worstScoreEl) worstScoreEl.textContent = data.worst_score || 0;
    } catch (error) {
        console.error("Error loading summary stats:", error);
    }
}

/**
 * Format date string to short format (e.g., "Mar 10")
 */
function formatDateShort(dateStr) {
    const date = new Date(dateStr + 'T00:00:00');
    const options = { month: 'short', day: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

/**
 * Format condition name from snake_case to title case
 */
function formatConditionName(name) {
    return name
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join('-');
}

/**
 * Initialize all charts when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function() {
    // Check if Chart.js library is available
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js library not found. Skipping chart initialization.');
        return;
    }

    initTrendsChart();
    initRadarChart();
    loadSummaryStats();
});

/**
 * Reinitialize charts (for use if data updates)
 */
function reinitializeCharts() {
    initTrendsChart();
    initRadarChart();
    loadSummaryStats();
}
