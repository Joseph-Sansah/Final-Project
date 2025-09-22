document.addEventListener('DOMContentLoaded', function() {
    // Example logs - replace with backend fetch
    let logs = [
       
       
    ];

    const logsTableBody = document.getElementById('logs-table-body');
    const searchInput = document.getElementById('search-log');
    const filterAction = document.getElementById('filter-action');

    function renderLogs() {
        const filterText = searchInput.value.trim().toLowerCase();
        const filterAct = filterAction.value;
        logsTableBody.innerHTML = "";
        logs
            .filter(log =>
                (filterAct === "" || log.action === filterAct) &&
                (
                    log.datetime.toLowerCase().includes(filterText) ||
                    log.user.toLowerCase().includes(filterText) ||
                    log.action.toLowerCase().includes(filterText) ||
                    log.details.toLowerCase().includes(filterText)
                )
            )
            .forEach(log => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${log.datetime}</td>
                    <td>${log.user}</td>
                    <td>${log.action}</td>
                    <td>${log.details}</td>
                `;
                logsTableBody.appendChild(tr);
            });
    }

    renderLogs();

    searchInput.addEventListener('input', renderLogs);
    filterAction.addEventListener('change', renderLogs);

    // Optional: Highlight active nav link
    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => {
        if (window.location.pathname.endsWith(link.getAttribute('href'))) {
            link.classList.add('active');
        }
    });
    document.addEventListener("DOMContentLoaded", function () {
  console.log("Audit log page loaded");
});

// Optional: Highlight rows based on recent timestamps
document.addEventListener("DOMContentLoaded", () => {
  const rows = document.querySelectorAll(".audit-table tbody tr");
  rows.forEach(row => {
    const timestampCell = row.cells[row.cells.length - 1];
    if (timestampCell) {
      const date = new Date(timestampCell.textContent);
      const now = new Date();
      const diffHours = Math.abs(now - date) / 36e5;
      if (diffHours < 24) {
        row.style.backgroundColor = "#e6f7ff";
      }
    }
  });
});


});