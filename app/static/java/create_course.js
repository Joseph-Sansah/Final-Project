document.addEventListener('DOMContentLoaded', () => {
    const deleteButtons = document.querySelectorAll('.delete-btn');
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modalTitle');
    const modalMessage = document.getElementById('modalMessage');
    const modalCloseBtn = document.getElementById('modalCloseBtn');

    deleteButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const courseId = button.getAttribute('data-id');
            const courseCard = button.closest('.relative');

            if (!confirm("Are you sure you want to delete this course?")) return;

            try {
                const response = await fetch(`/delete_course/${courseId}`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                const result = await response.json();

                if (result.success) {
                    courseCard.remove();
                    showModal("Course Deleted", "The course was successfully removed.");
                } else {
                    showModal("Deletion Failed", result.message || "Unable to delete the course.");
                }
            } catch (error) {
                console.error("Error deleting course:", error);
                showModal("Error", "An unexpected error occurred.");
            }
        });
    });

    modalCloseBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
    });

    function showModal(title, message) {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modal.classList.remove('hidden');
    }
});



