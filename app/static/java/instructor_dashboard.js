document.addEventListener('DOMContentLoaded', () => {
    // Tab switching functionality
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to the clicked button and its corresponding content
            button.classList.add('active');
            const targetTabId = button.getAttribute('onclick').match(/'(.*)'/)[1];
            document.getElementById(targetTabId).classList.add('active');

            // Re-render the chart if the "Group Performance" tab is active
            if (targetTabId === 'group-performance') {
                renderGroupPerformanceChart();
            }
        });
    });
    
    // Initial call to render the default active tab's content
    const initialActiveTab = document.querySelector('.tab-button.active');
    if (initialActiveTab) {
        const targetTabId = initialActiveTab.getAttribute('onclick').match(/'(.*)'/)[1];
        document.getElementById(targetTabId).classList.add('active');
    }

    // Initial chart render (if the default tab is "Group Performance")
    if (document.getElementById('group-performance').classList.contains('active')) {
        renderGroupPerformanceChart();
    }
});


  document.addEventListener('DOMContentLoaded', () => {
    const profileMenu = document.querySelector('.profile-menu');
    const profileImage = profileMenu.querySelector('img');

    profileImage.addEventListener('click', (e) => {
      e.stopPropagation(); // Prevent bubbling
      profileMenu.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!profileMenu.contains(e.target)) {
        profileMenu.classList.remove('open');
      }
    });
  });

