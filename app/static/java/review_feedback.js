document.addEventListener('DOMContentLoaded', function() {
    // Example feedback - replace with backend fetch
    let feedbacks = [
       
    ];

    const feedbackTableBody = document.getElementById('feedback-table-body');
    const searchInput = document.getElementById('search-feedback');
    const filterType = document.getElementById('filter-type');

    function renderFeedbacks() {
        const filterText = searchInput.value.trim().toLowerCase();
        const filterT = filterType.value;
        feedbackTableBody.innerHTML = "";
        feedbacks
            .filter(f =>
                (filterT === "" || f.type === filterT) &&
                (
                    f.date.toLowerCase().includes(filterText) ||
                    f.from.toLowerCase().includes(filterText) ||
                    f.type.toLowerCase().includes(filterText) ||
                    f.feedback.toLowerCase().includes(filterText) ||
                    f.status.toLowerCase().includes(filterText)
                )
            )
            .forEach(f => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${f.date}</td>
                    <td>${f.from}</td>
                    <td>${f.type}</td>
                    <td>${f.feedback}</td>
                    <td>${f.status}</td>
                    <td>
                        <div class="feedback-actions-table">
                            <button class="resolve-btn"${f.status === "Resolved" ? " disabled" : ""}>Resolve</button>
                            <button class="delete-btn">Delete</button>
                        </div>
                    </td>
                `;
                // Resolve
                tr.querySelector('.resolve-btn').addEventListener('click', function() {
                    if (f.status !== "Resolved") {
                        f.status = "Resolved";
                        renderFeedbacks();
                    }
                });
                // Delete
                tr.querySelector('.delete-btn').addEventListener('click', function() {
                    if (confirm(`Delete feedback from "${f.from}"?`)) {
                        feedbacks = feedbacks.filter(fb => fb.id !== f.id);
                        renderFeedbacks();
                    }
                });
                feedbackTableBody.appendChild(tr);
            });
    }

    renderFeedbacks();

    searchInput.addEventListener('input', renderFeedbacks);
    filterType.addEventListener('change', renderFeedbacks);

    // Optional: Highlight active nav link
    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => {
        if (window.location.pathname.endsWith(link.getAttribute('href'))) {
            link.classList.add('active');
        }
    });
    
        searchInput.addEventListener('input', filterFeedback);
        filterStatus.addEventListener('change', filterFeedback);

        function filterFeedback() {
            const keyword = searchInput.value.toLowerCase();
            const status = filterStatus.value;

            [...tableBody.rows].forEach(row => {
                const text = row.innerText.toLowerCase();
                const match = text.includes(keyword);
                const matchStatus = !status || text.includes(status.toLowerCase());
                row.style.display = (match && matchStatus) ? '' : 'none';
            });
        }
});