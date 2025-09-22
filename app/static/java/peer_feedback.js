  const currentUserId = "{{ session.get('user_id') }}";  // Injected from Flask
  let activePeerId = null;
  let chatHistory = {};  // { peerId: [ { sender, text, time } ] }

  // 🟡 Start Chat
  function startChat(peerId, peerName) {
    activePeerId = peerId;
    document.getElementById('chat-header').textContent = `Chat with ${peerName}`;
    document.getElementById('message-input-panel').classList.remove('hidden');
    renderChat(peerId);
  }

  // 🟢 Render Chat History
  function renderChat(peerId) {
    const feed = document.getElementById('chat-feed');
    feed.innerHTML = '';
    const messages = chatHistory[peerId] || [];
    messages.forEach(msg => {
      const bubble = document.createElement('div');
      bubble.className = `flex ${msg.sender === currentUserId ? 'justify-end' : 'justify-start'}`;
      bubble.innerHTML = `
        <div class="${msg.sender === currentUserId ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'} px-4 py-2 rounded-xl max-w-xs text-sm shadow">
          ${msg.text}
          <div class="text-[10px] text-right mt-1 opacity-70">${msg.time}</div>
        </div>
      `;
      feed.appendChild(bubble);
    });
    feed.scrollTop = feed.scrollHeight;
  }

  // 📨 Send Message
  document.getElementById('send-message-btn').addEventListener('click', () => {
    const input = document.getElementById('message-input');
    const text = input.value.trim();
    if (!text || !activePeerId) return;

    const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    const msg = { sender: currentUserId, text, time };

    chatHistory[activePeerId] = chatHistory[activePeerId] || [];
    chatHistory[activePeerId].push(msg);
    input.value = '';
    renderChat(activePeerId);

    // TODO: Send to backend via fetch
    // fetch('/send_message', { method: 'POST', body: JSON.stringify({ to: activePeerId, text }) })
  });

  // ✍️ Typing Indicator
  document.getElementById('message-input').addEventListener('input', () => {
    document.getElementById('typing-indicator').classList.remove('hidden');
    clearTimeout(window.typingTimeout);
    window.typingTimeout = setTimeout(() => {
      document.getElementById('typing-indicator').classList.add('hidden');
    }, 1000);
  });

  // 💡 Post Suggestion
  document.getElementById('post-suggestion-btn').addEventListener('click', () => {
    const input = document.getElementById('suggestion-input');
    const text = input.value.trim();
    if (!text) return;

    const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    const suggestion = { sender: "You", text, time };
    renderNewSuggestion(suggestion);
    input.value = '';

    // TODO: Send to backend
    // fetch('/post_suggestion', { method: 'POST', body: JSON.stringify({ text }) })
  });

  // 🧠 Render New Suggestion (Client-side only)
  function renderNewSuggestion(s) {
    const feed = document.getElementById('suggestion-feed');
    const div = document.createElement('div');
    div.className = "bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-lg shadow-sm";
    div.innerHTML = `
      <div class="font-semibold text-gray-800">${s.sender}</div>
      <p class="text-gray-700 mt-1">${s.text}</p>
      <div class="text-xs text-gray-500 mt-2">🕒 ${s.time} | 👍 0 likes</div>
      <div class="mt-3 pl-4 border-l border-gray-300 text-sm text-gray-500">No comments yet.</div>
    `;
    feed.prepend(div);
  }

  // 🤝 Invite Peer to Collaborate
  function inviteToCollaborate(peerId) {
    alert("Collaboration invite sent to user " + peerId);
    // TODO: Send to backend
    // fetch('/invite_peer', { method: 'POST', body: JSON.stringify({ peer_id: peerId }) })
  }

  // 🧩 Attach event listeners to dynamic buttons
  document.querySelectorAll('[data-chat-peer]').forEach(btn => {
    btn.addEventListener('click', () => {
      const peerId = btn.getAttribute('data-chat-peer');
      const peerName = btn.getAttribute('data-peer-name');
      startChat(peerId, peerName);
    });
  });

  document.querySelectorAll('[data-invite-peer]').forEach(btn => {
    btn.addEventListener('click', () => {
      const peerId = btn.getAttribute('data-invite-peer');
      inviteToCollaborate(peerId);
    });
  });

