document.addEventListener('DOMContentLoaded', () => {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(msg => {
        msg.style.transition = 'opacity 0.5s';
        setTimeout(() => {
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 1000);
        }, 4000);
    });

    // Confirm assignment submission (students)
    const studentForm = document.querySelector('form textarea[name="content"]');
    if (studentForm) {
        studentForm.closest('form').addEventListener('submit', function (e) {
            if (!confirm("Are you sure you want to submit your assignment?")) {
                e.preventDefault();
            }
        });
    }

    // Instructor grading forms
    document.querySelectorAll('form input[name="submission_id"]').forEach(input => {
        const form = input.closest('form');
        form.addEventListener('submit', function (e) {
            if (!confirm("Submit this grade and feedback?")) {
                e.preventDefault();
            }
        });
    });

    // Peer feedback forms
    document.querySelectorAll('form input[name="peer_feedback"]').forEach(input => {
        const form = input.closest('form');
        const scoreInput = form.querySelector('input[name="score"]');

        form.addEventListener('submit', function (e) {
            const score = parseInt(scoreInput.value);
            if (isNaN(score) || score < 1 || score > 5) {
                alert("Peer score must be between 1 and 5.");
                e.preventDefault();
                return;
            }

            if (!confirm("Submit your peer feedback?")) {
                e.preventDefault();
            }
        });
    });

    // Highlight and scroll to current user's submission
    const currentUserId = document.body.getAttribute('data-user-id');
    if (currentUserId) {
        const submissions = document.querySelectorAll('li[data-student-id]');
        submissions.forEach(sub => {
            if (sub.getAttribute('data-student-id') === currentUserId) {
                sub.style.backgroundColor = '#f0f8ff';
                sub.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }
});
