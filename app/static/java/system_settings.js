document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('settings-form');
    const successMsg = document.getElementById('settings-success');

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        // Here you would send updated settings to your backend
        successMsg.style.display = 'block';
        setTimeout(() => { successMsg.style.display = 'none'; }, 1800);
    });

    // Optional: Highlight active nav link
    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => {
        if (window.location.pathname.endsWith(link.getAttribute('href'))) {
            link.classList.add('active');
        }
    });
});
document.addEventListener('DOMContentLoaded', function() {
    const successMsg = document.getElementById('settings-success');
    const summary = document.getElementById('settings-summary');

    function updateSummary() {z
        summary.innerHTML = `
            <h3>Current Settings</h3>
            <ul>
                <li><strong>Platform Name:</strong> ${document.getElementById('platform-name').value}</li>
                <li><strong>Allow Registration:</strong> ${document.getElementById('allow-registration').value === 'yes' ? 'Yes' : 'No'}</li>
                <li><strong>Default User Role:</strong> ${document.getElementById('default-role').value}</li>
                <li><strong>Maintenance Mode:</strong> ${document.getElementById('maintenance-mode').value === 'on' ? 'On' : 'Off'}</li>
            </ul>
        `;
    }

    updateSummary();

    form.addEventListener('input', updateSummary);

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        // Here you would send updated settings to your backend
        successMsg.style.display = 'block';
        setTimeout(() => { successMsg.style.display = 'none'; }, 1800);
        updateSummary();
    });

    // Optional: Highlight active nav link
    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => {
        if (window.location.pathname.endsWith(link.getAttribute('href'))) {
            link.classList.add('active');
        }
    });

    // Auto-fill current year if template fails
document.addEventListener("DOMContentLoaded", () => {
  const yearSpan = document.getElementById("year");
  if (yearSpan && !yearSpan.textContent.trim()) {
    yearSpan.textContent = new Date().getFullYear();
  }
});

// Optional: Confirm before saving settings
const form = document.querySelector(".settings-form");
if (form) {
  form.addEventListener("submit", (e) => {
    const confirmed = confirm("Are you sure you want to save these settings?");
    if (!confirmed) e.preventDefault();
  });
}
const toggle = document.getElementById('darkModeToggle');
toggle.addEventListener('change', () => {
  document.body.classList.toggle('dark-mode');
});


});