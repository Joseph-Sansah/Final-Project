document.addEventListener('DOMContentLoaded', () => {
  // Get chart data from a global variable injected by Flask
  const chartData = window.analyticsCharts;

  if (!chartData) {
    console.warn('No chart data available.');
    return;
  }

  // Helper to render a chart
  function renderChart(id, label, labels, values, type = 'line') {
    const ctx = document.getElementById(id);
    if (!ctx) return;

    new Chart(ctx, {
      type: type,
      data: {
        labels: labels,
        datasets: [{
          label: label,
          data: values,
          backgroundColor: 'rgba(52, 152, 219, 0.2)',
          borderColor: 'rgba(52, 152, 219, 1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  }

  // Render each chart
  renderChart(
    'userEngagementChart',
    'Daily Engagement',
    chartData.user_engagement.map(d => d.day),
    chartData.user_engagement.map(d => d.count)
  );

  renderChart(
    'feedbackChart',
    'Avg Feedback',
    chartData.feedback_sentiment.map(d => d.day),
    chartData.feedback_sentiment.map(d => d.avg_rating)
  );

  renderChart(
    'pageVisitsChart',
    'Page Visits',
    chartData.page_visits.map(d => d.page),
    chartData.page_visits.map(d => d.visits),
    'bar'
  );

  renderChart(
    'userGrowthChart',
    'New Users',
    chartData.user_growth.map(d => `Week ${d.week}`),
    chartData.user_growth.map(d => d.new_users)
  );
});
