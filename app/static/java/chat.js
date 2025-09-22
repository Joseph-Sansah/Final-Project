// static/js/chat.js

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Socket.IO connection
    // The server URL is automatically inferred by Socket.IO
    const socket = io();

    // Get DOM elements
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const onlinePeersList = document.getElementById('online-peers');

    // Get current user ID from a hidden data attribute in your HTML
    // This requires adding a hidden field or data attribute to your template
    // <body data-user-id="{{ current_user.id }}">
    const currentUserId = document.body.dataset.userId;

    // Function to scroll chat to the bottom
    const scrollToBottom = () => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    // Function to create a new message element
    const createMessageElement = (message) => {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        if (message.user_id === parseInt(currentUserId)) {
            messageDiv.classList.add('self');
        }

        const formattedTime = new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        messageDiv.innerHTML = `
            <img src="${message.profile_image}" alt="User avatar" class="avatar">
            <div class="message-bubble">
                <strong class="author">${message.full_name}</strong>
                <p class="text">${message.message_text}</p>
                <small class="timestamp">${formattedTime}</small>
            </div>
        `;
        return messageDiv;
    };

    // 2. Handle receiving a new message from the server
    socket.on('message_update', (data) => {
        const newMessageElement = createMessageElement(data);
        chatMessages.appendChild(newMessageElement);
        scrollToBottom();
    });

    // 3. Handle a user sending a message
    const sendMessage = () => {
        const messageText = messageInput.value.trim();
        if (messageText) {
            // Emit the message to the server
            socket.emit('new_message', {
                user_id: currentUserId,
                message_text: messageText,
                // You may also want to send user details to avoid a server lookup
                full_name: "{{ current_user.full_name }}",
                profile_image: "{{ current_user.profile_image }}"
            });
            messageInput.value = ''; // Clear the input field
        }
    };

    // Attach event listeners
    sendBtn.addEventListener('click', sendMessage);

    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Initial scroll to the bottom when the page loads
    scrollToBottom();
});