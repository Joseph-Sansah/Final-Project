document.addEventListener('DOMContentLoaded', () => {
  // Animate cards on hover
  const cards = document.querySelectorAll('.card');
  cards.forEach(card => {
    card.addEventListener('mouseenter', () => card.classList.add('hovered'));
    card.addEventListener('mouseleave', () => card.classList.remove('hovered'));
  });

  // Role-based UI toggle
  const userRole = sessionStorage.getItem('userRole'); // e.g., 'superadmin', 'admin', 'viewer'
  const restrictedElements = document.querySelectorAll('[data-role="superadmin-only"]');

  if (userRole !== 'superadmin') {
    restrictedElements.forEach(el => el.style.display = 'none');
  }

  // Dynamic content loading (example: audit logs)
  const logsBtn = document.querySelector('.card-button[href*="audit_logs"]');
  if (logsBtn) {
    logsBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const logsContainer = document.createElement('div');
      logsContainer.className = 'logs-preview';
      logsContainer.innerText = 'Loading logs...';
      document.querySelector('.dashboard-content').appendChild(logsContainer);

      try {
        const response = await fetch('/api/audit_logs');
        const data = await response.json();
        logsContainer.innerHTML = `<ul>${data.logs.map(log => `<li>${log}</li>`).join('')}</ul>`;
      } catch (error) {
        logsContainer.innerText = 'Failed to load logs.';
        console.error('Audit log fetch error:', error);
      }
    });
  }
});
