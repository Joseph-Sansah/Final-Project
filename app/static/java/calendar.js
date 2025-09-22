
  // Safely pass Python data to JS using Flask's tojson filter
  

  document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');

    const calendar = new FullCalendar.Calendar(calendarEl, {
      initialView: 'dayGridMonth',
      headerToolbar: {
        left: 'prev,next today',
        center: 'title',
        right: ''
      },
      events: calendarEvents,
      eventClick: function(info) {
        const date = info.event.start.toISOString().split('T')[0];
        alert(`${info.event.title}\nDate: ${date}`);
      }
    });

    calendar.render();
  });

