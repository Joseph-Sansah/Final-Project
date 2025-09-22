// === Theme Toggle Logic ===
        const themeToggleBtn = document.getElementById('theme-toggle');
        const lightIcon = document.getElementById('theme-toggle-light-icon');
        const darkIcon = document.getElementById('theme-toggle-dark-icon');
        const htmlElement = document.documentElement;

        // Check for saved theme in localStorage or prefer system setting
        const currentTheme = localStorage.getItem('color-theme');
        if (currentTheme) {
            htmlElement.classList.add(currentTheme);
        } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            htmlElement.classList.add('dark');
        } else {
            htmlElement.classList.add('light');
        }

        // Initialize icon state
        if (htmlElement.classList.contains('dark')) {
            lightIcon.classList.add('hidden');
            darkIcon.classList.remove('hidden');
            document.body.classList.add('dark:bg-gray-900', 'dark:text-gray-100');
            document.body.classList.remove('bg-gray-100', 'text-gray-900');
        } else {
            lightIcon.classList.remove('hidden');
            darkIcon.classList.add('hidden');
            document.body.classList.remove('dark:bg-gray-900', 'dark:text-gray-100');
            document.body.classList.add('bg-gray-100', 'text-gray-900');
        }

        // Add click event listener to toggle theme
        themeToggleBtn.addEventListener('click', function() {
            // Toggle HTML class
            htmlElement.classList.toggle('dark');
            htmlElement.classList.toggle('light');

            // Toggle body classes for transitions
            document.body.classList.toggle('dark:bg-gray-900');
            document.body.classList.toggle('dark:text-gray-100');
            document.body.classList.toggle('bg-gray-100');
            document.body.classList.toggle('text-gray-900');

            // Toggle icons
            lightIcon.classList.toggle('hidden');
            darkIcon.classList.toggle('hidden');

            // Save the new theme to localStorage
            if (htmlElement.classList.contains('dark')) {
                localStorage.setItem('color-theme', 'dark');
            } else {
                localStorage.setItem('color-theme', 'light');
            }
        });

        // === Progress Chart Logic ===
        const ctx = document.getElementById('progressChart').getContext('2d');
        const progressChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
                datasets: [{
                    label: 'Assignment Score',
                    data: [75, 80, 85, 92, 88, 95],
                    backgroundColor: 'rgba(59, 130, 246, 0.2)', // Blue 500 with opacity
                    borderColor: 'rgba(59, 130, 246, 1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: {
                            color: 'rgba(229, 231, 235, 0.2)' // Adjust grid color for dark mode
                        },
                        ticks: {
                            color: 'rgba(156, 163, 175, 1)' // Adjust tick color for dark mode
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(229, 231, 235, 0.2)' // Adjust grid color for dark mode
                        },
                        ticks: {
                            color: 'rgba(156, 163, 175, 1)' // Adjust tick color for dark mode
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: 'rgba(156, 163, 175, 1)' // Adjust legend text color for dark mode
                        }
                    }
                }
            }
        });

        // Update chart colors based on theme changes
        function updateChartColors() {
            const isDarkMode = document.documentElement.classList.contains('dark');
            const gridColor = isDarkMode ? 'rgba(55, 65, 81, 1)' : 'rgba(229, 231, 235, 1)';
            const tickAndLabelColor = isDarkMode ? 'rgba(156, 163, 175, 1)' : 'rgba(107, 114, 128, 1)';
            
            progressChart.options.scales.x.grid.color = gridColor;
            progressChart.options.scales.y.grid.color = gridColor;
            progressChart.options.scales.x.ticks.color = tickAndLabelColor;
            progressChart.options.scales.y.ticks.color = tickAndLabelColor;
            progressChart.options.plugins.legend.labels.color = tickAndLabelColor;
            progressChart.update();
        }

        // Listen for theme changes to update the chart
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName === 'class') {
                    updateChartColors();
                }
            });
        });

        observer.observe(document.documentElement, { attributes: true });

        // Initial chart color update
        updateChartColors();

// === Progress Chart Initialization ===
    document.addEventListener("DOMContentLoaded", function () {
        const ctx = document.getElementById('progressChart').getContext('2d');

        const labels = { progress_labels , tojson };
        const progress_scores = { progress_scores , tojson };
        const scores = { progress_scores , tojson };

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Performance Score',
                    data: scores,
                    borderColor: '#3B82F6',
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#1D4ED8',
                    pointRadius: 5,
                    pointHoverRadius: 7
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: true },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 10 }
                    }
                }
            }
        });
    });

