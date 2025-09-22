document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('assignments-container');

    // Load assignments from backend
    function loadAssignments() {
        fetch('/api/student_assignments')
            .then(response => response.json())
            .then(assignments => {
                container.innerHTML = '';
                if (!assignments.length) {
                    container.innerHTML = '<p>No assignments found.</p>';
                    return;
                }

                assignments.forEach(assignment => {
                    const card = document.createElement('div');
                    card.className = 'assignment-card';
                    card.innerHTML = `
                        <div class="assignment-title"><strong>${assignment.title}</strong></div>
                        <div class="assignment-desc">${assignment.description}</div>
                        <div class="assignment-meta">Due: ${assignment.due_date}</div>
                        <form class="assignment-form" data-id="${assignment.id}" enctype="multipart/form-data">
                            <textarea name="text_submission" rows="4" placeholder="Write your answer here (optional)"></textarea>
                            <input type="file" name="file_submission" accept=".pdf,.doc,.docx,.txt">
                            <button type="submit">Submit Assignment</button>
                            <span class="success-msg" style="display:none; color: green;">Submitted!</span>
                            <span class="error-msg" style="display:none; color: red;">Error submitting.</span>
                        </form>
                    `;
                    container.appendChild(card);
                });

                bindFormEvents();
            })
            .catch(err => {
                console.error("Failed to load assignments:", err);
                container.innerHTML = '<p>Error loading assignments.</p>';
            });
    }

    // Bind form submission events
    function bindFormEvents() {
        document.querySelectorAll('.assignment-form').forEach(form => {
            form.addEventListener('submit', function (e) {
                e.preventDefault();

                const formData = new FormData(form);
                const assignmentId = form.getAttribute('data-id');

                fetch(`/api/submit_assignment/${assignmentId}`, {
                    method: 'POST',
                    body: formData
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            form.querySelector('.success-msg').style.display = 'inline';
                            form.querySelector('.error-msg').style.display = 'none';
                            form.reset();
                            setTimeout(() => {
                                form.querySelector('.success-msg').style.display = 'none';
                            }, 2000);
                        } else {
                            form.querySelector('.error-msg').textContent = data.message || 'Submission failed.';
                            form.querySelector('.error-msg').style.display = 'inline';
                        }
                    })
                    .catch(err => {
                        console.error("Submission error:", err);
                        form.querySelector('.error-msg').style.display = 'inline';
                    });
            });
        });
    }

    loadAssignments();
});
