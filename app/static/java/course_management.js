// Sample dummy courses (can replace with fetch from backend)
let courses = [
  {
    title: "Intro to Web Development",
    description: "Learn HTML, CSS, and JavaScript basics."
  },
  {
    title: "Collaborative Writing",
    description: "Explore peer-based editing and critique techniques."
  }
];

// DOM Elements
const modal = document.getElementById("courseModal");
const courseForm = document.getElementById("courseForm");
const coursesList = document.getElementById("courses-list");

// Load courses on page load
document.addEventListener("DOMContentLoaded", () => {
  renderCourses();
});

// Modal Functions
function openModal() {
  modal.style.display = "block";
}

function closeModal() {
  modal.style.display = "none";
  courseForm.reset();
}

// Form Submit
courseForm.addEventListener("submit", function (e) {
  e.preventDefault();
  const title = document.getElementById("courseTitle").value;
  const description = document.getElementById("courseDescription").value;

  // Add to course array
  courses.push({ title, description });

  // Re-render list
  renderCourses();
  closeModal();
});

// Render courses list
function renderCourses() {
  coursesList.innerHTML = "";
  courses.forEach(course => {
    const li = document.createElement("li");
    li.innerHTML = `<h4>${course.title}</h4><p>${course.description}</p>`;
    coursesList.appendChild(li);
  });
}

// Close modal on outside click
window.addEventListener("click", function (e) {
  if (e.target == modal) {
    closeModal();
  }
});
