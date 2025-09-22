document.addEventListener('DOMContentLoaded', function() {
    // Example: Load user data (replace with backend fetch)
    const user = {
       
    };

    const nameInput = document.getElementById('profile-name');
    const emailInput = document.getElementById('profile-email');
    const roleInput = document.getElementById('profile-role');
    const avatarImg = document.getElementById('profile-avatar');
    const form = document.getElementById('profile-form');
    const successMsg = document.getElementById('profile-success');

    // Populate fields
    nameInput.value = user.name;
    emailInput.value = user.email;
    roleInput.value = user.role;
    avatarImg.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=8e44ad&color=fff&size=128`;

    // Update avatar on name change
    nameInput.addEventListener('input', function() {
        avatarImg.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(nameInput.value)}&background=8e44ad&color=fff&size=128`;
    });

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        // Here you would send updated data to your backend
        successMsg.style.display = 'block';
        setTimeout(() => { successMsg.style.display = 'none'; }, 1800);
    });
});