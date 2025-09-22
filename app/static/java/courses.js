document.addEventListener('DOMContentLoaded', function() {
    // Example data - replace with fetch from backend
    let courses = [
        
    ];

    const container = document.getElementById('courses-container');
    const searchInput = document.getElementById('search-input');

    function renderCourses(filter = "") {
        container.innerHTML = "";
        courses
            .filter(course =>
                course.name.toLowerCase().includes(filter) ||
                course.code.toLowerCase().includes(filter) ||
                course.description.toLowerCase().includes(filter)
            )
            .forEach(course => {
                const card = document.createElement('div');
                card.className = 'course-card';
                card.innerHTML = `
                    <div class="course-title">${course.name}</div>
                    <div class="course-code">${course.code}</div>
                    <div class="course-desc">${course.description}</div>
                    <div class="course-actions">
                        <a href="assignments.html?course=${encodeURIComponent(course.code)}">View Assignments</a>
                        ${course.enrolled
                            ? `<button class="enroll-btn" disabled>Enrolled</button>`
                            : `<button class="enroll-btn">Enroll</button>`
                        }
                    </div>
                `;
                // Enroll button logic
                const enrollBtn = card.querySelector('.enroll-btn');
                if (enrollBtn && !course.enrolled) {
                    enrollBtn.addEventListener('click', function() {
                        course.enrolled = true;
                        enrollBtn.textContent = "Enrolled";
                        enrollBtn.disabled = true;
                        enrollBtn.style.background = "#27ae60";
                    });
                }
                container.appendChild(card);
            });
    }

    renderCourses();

    searchInput.addEventListener('input', function() {
        renderCourses(searchInput.value.trim().toLowerCase());
    });
});