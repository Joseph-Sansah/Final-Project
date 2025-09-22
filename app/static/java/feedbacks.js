// Emoji Picker Setup
document.addEventListener('DOMContentLoaded', () => {
    const emojiButtons = document.querySelectorAll('.emoji-btn');

    emojiButtons.forEach(button => {
        const picker = new EmojiButton({
            position: 'top-start'
        });

        button.addEventListener('click', () => {
            picker.togglePicker(button);
        });

        picker.on('emoji', emoji => {
            const textarea = button.previousElementSibling || button.closest('.emoji-wrapper').querySelector('textarea');
            textarea.value += emoji;
        });
    });

    // Show success message after feedback is submitted
    const feedbackForm = document.getElementById('feedback-form');
    if (feedbackForm) {
        feedbackForm.addEventListener('submit', () => {
            setTimeout(() => {
                const successMsg = document.getElementById('feedback-success');
                if (successMsg) successMsg.style.display = 'block';
            }, 300); // Adjust timing if needed
        });
    }
});

// Like Feedback Function
function likeFeedback(feedbackId, element) {
    fetch(`/like_feedback/${feedbackId}`, {
        method: 'POST'
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            element.classList.add('liked');
            element.innerHTML = `<i class="fas fa-thumbs-up"></i> Liked (${data.likes})`;
        } else {
            alert(data.message || 'Unable to like feedback.');
        }
    })
    .catch(err => {
        console.error('Error:', err);
        alert('Something went wrong.');
    });
}

window.addEventListener('DOMContentLoaded', () => {
  const buttons = document.querySelectorAll('.emoji-btn');
  const pickers = [];

  buttons.forEach((btn, index) => {
    const picker = new EmojiButton({ position: 'top-end' });
    pickers.push(picker);

    picker.on('emoji', emoji => {
      const textarea = btn.closest('.emoji-wrapper').querySelector('textarea');
      textarea.value += emoji;
    });

    btn.addEventListener('click', () => {
      picker.togglePicker(btn);
    });
  });
});


document.addEventListener('DOMContentLoaded', () => {
  const emojiBtns = document.querySelectorAll('.emoji-btn');

  emojiBtns.forEach(btn => {
    const picker = new EmojiButton({ position: 'top-end' });
    
    picker.on('emoji', emoji => {
      const textarea = btn.closest('.emoji-wrapper').querySelector('textarea');
      textarea.value += emoji;
    });

    btn.addEventListener('click', () => picker.togglePicker(btn));
  });
});

