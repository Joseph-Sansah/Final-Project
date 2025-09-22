document.addEventListener('DOMContentLoaded', function() {
   
    let assignments = [
       
    ];
    let editingAssignmentId = null;

    const assignmentTableBody = document.getElementById('assignment-table-body');
    const searchInput = document.getElementById('search-assignment');
    const addAssignmentBtn = document.getElementById('add-assignment-btn');
    const assignmentModal = document.getElementById('assignment-modal');
    const closeModal = document.getElementById('close-modal');
    const assignmentForm = document.getElementById('assignment-form');
    const modalTitle = document.getElementById('modal-title');
    const titleInput = document.getElementById('assignment-title');
    const courseInput = document.getElementById('assignment-course');
    const descInput = document.getElementById('assignment-desc');
    const dueInput = document.getElementById('assignment-due');
    const statusInput = document.getElementById('assignment-status');

    function renderAssignments(filter = "") {
        assignmentTableBody.innerHTML = "";
        assignments
            .filter(a =>
                a.title.toLowerCase().includes(filter) ||
                a.course.toLowerCase().includes(filter) ||
                a.desc.toLowerCase().includes(filter) ||
                a.status.toLowerCase().includes(filter)
            )
            .forEach(a => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${a.title}</td>
                    <td>${a.course}</td>
                    <td>${a.due}</td>
                    <td>${a.status}</td>
                    <td>
                        <div class="assignment-actions-table">
                            <button class="edit-btn">Edit</button>
                            <button class="delete-btn">Delete</button>
                        </div>
                    </td>
                `;
                // Edit
                tr.querySelector('.edit-btn').addEventListener('click', function() {
                    editingAssignmentId = a.id;
                    modalTitle.textContent = "Edit Assignment";
                    titleInput.value = a.title;
                    courseInput.value = a.course;
                    descInput.value = a.desc;
                    dueInput.value = a.due;
                    statusInput.value = a.status;
                    assignmentModal.classList.add('open');
                });
                // Delete
                tr.querySelector('.delete-btn').addEventListener('click', function() {
                    if (confirm(`Delete assignment "${a.title}"?`)) {
                        assignments = assignments.filter(asg => asg.id !== a.id);
                        renderAssignments(searchInput.value.trim().toLowerCase());
                    }
                });
                assignmentTableBody.appendChild(tr);
            });
    }

    renderAssignments();

    searchInput.addEventListener('input', function() {
        renderAssignments(searchInput.value.trim().toLowerCase());
    });

    addAssignmentBtn.addEventListener('click', function() {
        editingAssignmentId = null;
        modalTitle.textContent = "Add Assignment";
        assignmentForm.reset();
        assignmentModal.classList.add('open');
    });

    closeModal.addEventListener('click', function() {
        assignmentModal.classList.remove('open');
    });

    assignmentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const title = titleInput.value.trim();
        const course = courseInput.value.trim();
        const desc = descInput.value.trim();
        const due = dueInput.value;
        const status = statusInput.value;
        if (editingAssignmentId) {
            // Edit assignment
            assignments = assignments.map(a =>
                a.id === editingAssignmentId
                    ? { ...a, title, course, desc, due, status }
                    : a
            );
        } else {
            // Add assignment
            assignments.push({
                id: Date.now(),
                title,
                course,
                desc,
                due,
                status
            });
        }
        assignmentModal.classList.remove('open');
        renderAssignments(searchInput.value.trim().toLowerCase());
    });

    // Close modal on outside click
    window.addEventListener('click', function(e) {
        if (e.target === assignmentModal) {
            assignmentModal.classList.remove('open');
        }
    });
    
    document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const assignmentId = btn.dataset.id;
            editAssignment(assignmentId);
        });
    });

    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const assignmentId = btn.dataset.id;
            deleteAssignment(assignmentId);
        });
    });
});

});