document.addEventListener('DOMContentLoaded', () => {
    const addUserBtn = document.getElementById('add-user-btn');
    const editBtns = document.querySelectorAll('.edit-btn');
    const modal = document.getElementById('user-modal');
    const closeModal = document.getElementById('close-modal');
    const modalTitle = document.getElementById('modal-title');
    const userForm = document.getElementById('user-form');
    const userNameInput = document.getElementById('user-name');
    const userEmailInput = document.getElementById('user-email');
    const userRoleInput = document.getElementById('user-role');
    const userStatusInput = document.getElementById('user-status');
    const userPasswordInput = document.getElementById('user-password');
    const passwordLabel = document.getElementById('password-label');

    let editingUserId = null;

    // Open modal for adding a new user
    addUserBtn.addEventListener('click', () => {
        editingUserId = null;
        modalTitle.textContent = 'Add User';
        userNameInput.value = '';
        userEmailInput.value = '';
        userRoleInput.value = '';
        userStatusInput.value = 'Active';
        userPasswordInput.value = '';
        passwordLabel.style.display = 'block'; // Show password field for adding a user
        modal.style.display = 'flex';
    });

    // Open modal for editing an existing user
    editBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            editingUserId = btn.dataset.id;
            modalTitle.textContent = 'Edit User';
            userNameInput.value = btn.dataset.name;
            userEmailInput.value = btn.dataset.email;
            userRoleInput.value = btn.dataset.role;
            userStatusInput.value = btn.dataset.status;
            userPasswordInput.value = ''; // Password is not editable for existing users
            passwordLabel.style.display = 'none'; // Hide password field for editing a user
            modal.style.display = 'flex';
        });
    });

    // Close modal
    closeModal.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    // Save user (add or edit)
    userForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const name = userNameInput.value.trim();
        const email = userEmailInput.value.trim();
        const role = userRoleInput.value;
        const status = userStatusInput.value;
        const password = userPasswordInput.value.trim();

        if (!name || !email || !role || !status || (!editingUserId && !password)) {
            alert('All fields are required.');
            return;
        }

        const url = editingUserId ? `/edit_user/${editingUserId}` : '/add_user';
        const method = editingUserId ? 'PUT' : 'POST';

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ name, email, role, status, password }),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.status === 'success') {
                    alert(data.message);
                    location.reload(); // Reload the page to show the updated user list
                } else {
                    alert(data.message);
                }
            })
            .catch((error) => {
                console.error('Error:', error);
                alert('An error occurred while saving the user.');
            });
    });
});