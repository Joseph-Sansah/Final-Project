document.addEventListener('DOMContentLoaded', () => {
    // Handle Create Forum Form (if visible)
    const createForm = document.querySelector('form[action=""]');  // Since create form has no action
    if (createForm) {
        createForm.addEventListener('submit', (e) => {
            const topic = createForm.querySelector('input[name="topic"]');
            const desc = createForm.querySelector('textarea[name="description"]');
            const course = createForm.querySelector('select[name="course_id"]');

            if (!topic.value.trim() || !desc.value.trim() || !course.value) {
                e.preventDefault();
                alert("Please fill in all fields to create a forum.");
                return false;
            }
        });
    }

    // Handle Reply Forms
    const replyForms = document.querySelectorAll('form[action*="reply_forum"]');
    replyForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const textarea = form.querySelector('textarea[name="content"]');
            if (!textarea.value.trim()) {
                e.preventDefault();
                alert("Please write a reply before submitting.");
                return false;
            }
        });
    });

    // Handle Rating Forms (Instructor Only)
    const ratingForms = document.querySelectorAll('form[action*="rate_reply"]');
    ratingForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const select = form.querySelector('select[name="rating"]');
            if (!select.value) {
                e.preventDefault();
                alert("Please select a rating before submitting.");
                return false;
            }
        });
    });

    // Highlight forums if needed (optional enhancement)
    highlightForums();
});

function highlightForums() {
    const forumSections = document.querySelectorAll('.forum-thread');
    forumSections.forEach(section => {
        section.addEventListener('mouseenter', () => {
            section.classList.add('ring', 'ring-blue-300', 'shadow-lg');
        });
        section.addEventListener('mouseleave', () => {
            section.classList.remove('ring', 'ring-blue-300', 'shadow-lg');
        });
    });
}


document.addEventListener('DOMContentLoaded', () => {
    const role = document.body.dataset.role;  // Passed via data attribute in HTML
    const userId = document.body.dataset.userId;

    initCreateForumAJAX();
    initReplyFormsAJAX();
    initRatingFormsAJAX();
});

function initCreateForumAJAX() {
    const createForm = document.querySelector('#createForumForm');
    if (createForm) {
        createForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const topic = createForm.topic.value.trim();
            const description = createForm.description.value.trim();
            const course_id = createForm.course_id.value;

            if (!topic || !description || !course_id) {
                return alert('Please fill all fields.');
            }

            const response = await fetch('/create_forum', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ topic, description, course_id })
            });

            const result = await response.json();
            if (result.success) {
                alert('Forum created!');
                location.reload(); // Reload to display new forum. Or dynamically inject it.
            } else {
                alert('Error creating forum');
            }
        });
    }
}

function initReplyFormsAJAX() {
    document.querySelectorAll('.reply-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const content = form.querySelector('textarea').value.trim();
            const forumId = form.dataset.forumId;

            if (!content) return alert("Please enter a reply.");

            const response = await fetch(`/reply_forum/${forumId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ content })
            });

            const result = await response.json();
            if (result.success) {
                alert("Reply submitted!");
                location.reload();  // Or update the reply section dynamically
            } else {
                alert("Error submitting reply.");
            }
        });
    });
}

function initRatingFormsAJAX() {
    document.querySelectorAll('.rating-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const replyId = form.dataset.replyId;
            const rating = form.querySelector('select').value;

            if (!rating) return alert("Select a rating.");

            const response = await fetch(`/rate_reply/${replyId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ rating })
            });

            const result = await response.json();
            if (result.success) {
                alert("Rating submitted!");
                location.reload();  // Or update the rating text dynamically
            } else {
                alert("Error rating reply.");
            }
        });
    });
}

// Helper for CSRF token from cookie
function getCSRFToken() {
    const name = 'csrftoken';
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : '';
}

document.addEventListener('DOMContentLoaded', () => {
    const role = document.body.dataset.role;
    const userId = document.body.dataset.userId;

    if (role !== 'instructor') return;

    const form = document.querySelector('form');
    const forumContainer = document.querySelector('div > h2.text-2xl + div');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const topic = form.topic.value.trim();
        const description = form.description.value.trim();
        const courseId = form.course_id.value;

        if (!topic || !description || !courseId) {
            alert('Please fill in all fields and select a course.');
            return;
        }

        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ topic, description, course_id: courseId })
            });

            const result = await response.json();

            if (result.success) {
                alert(result.message);
                form.reset();
                addForumToPage(result.forum);
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error('Error creating forum:', error);
            alert('Something went wrong. Please try again.');
        }
    });

    function addForumToPage(forum) {
        const forumDiv = document.createElement('div');
        forumDiv.className = 'bg-gray-100 p-6 rounded-lg mb-6 shadow-md border border-gray-200';
        forumDiv.innerHTML = `
            <div class="border-b pb-3 mb-4">
                <h3 class="text-xl font-bold text-gray-800 mb-1">${forum.topic}</h3>
                <p class="text-sm text-gray-600">
                    <i class="fas fa-user mr-1"></i>${forum.author} |
                    <i class="fas fa-calendar-alt ml-3 mr-1"></i>${forum.created_at}
                </p>
            </div>
            <p class="text-gray-700 mb-4">${forum.description}</p>
            <div class="border-t pt-4 mt-4 border-gray-200">
                <h4 class="text-lg font-semibold text-gray-700 mb-3">💬 Replies:</h4>
                <p class="text-gray-500 italic">No replies yet.</p>
            </div>
        `;
        forumContainer.prepend(forumDiv);
    }
});
