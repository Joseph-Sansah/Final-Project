document.addEventListener('DOMContentLoaded', function() {
    // Mobile nav toggle
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links');
    navToggle.addEventListener('click', function() {
        navLinks.classList.toggle('open');
    });

    // Optional: Highlight active link
    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => {
        if (window.location.pathname.endsWith(link.getAttribute('href'))) {
            link.classList.add('active');
        }
    });
});