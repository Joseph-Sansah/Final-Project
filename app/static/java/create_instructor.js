document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form');
    const passwordInput = document.getElementById('password');

    // Create a toggle for password visibility
    const toggleBtn = document.createElement('span');
    toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i>';
    toggleBtn.style.cursor = 'pointer';
    toggleBtn.style.position = 'absolute';
    toggleBtn.style.right = '10px';
    toggleBtn.style.top = '50%';
    toggleBtn.style.transform = 'translateY(-50%)';
    toggleBtn.style.color = '#666';

    // Style container for relative positioning
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    passwordInput.parentElement.insertBefore(wrapper, passwordInput);
    wrapper.appendChild(passwordInput);
    wrapper.appendChild(toggleBtn);

    // Toggle password visibility
    toggleBtn.addEventListener('click', () => {
        const type = passwordInput.getAttribute('type');
        if (type === 'password') {
            passwordInput.setAttribute('type', 'text');
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
        } else {
            passwordInput.setAttribute('type', 'password');
            toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i>';
        }
    });

    // Optional: Confirmation before submission
    form.addEventListener('submit', function (e) {
        const confirmSubmit = confirm('Are you sure you want to create this instructor account?');
        if (!confirmSubmit) {
            e.preventDefault();
        }
    });
});
