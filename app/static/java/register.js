document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("register-form");
  const password = document.getElementById("password");
  const confirmPassword = document.getElementById("confirm_password");
  const error = document.getElementById("password-error");

  form.addEventListener("submit", function (e) {
    if (password.value !== confirmPassword.value) {
      e.preventDefault();
      error.style.display = "block";
    } else {
      error.style.display = "none";
    }
  });
});

function toggleAdminCode(select) {
  const adminCodeGroup = document.getElementById("admin-code-group");
  if (select.value === "admin") {
    adminCodeGroup.style.display = "block";
  } else {
    adminCodeGroup.style.display = "none";
  }
}
