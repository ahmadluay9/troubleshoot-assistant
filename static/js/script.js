document.addEventListener("DOMContentLoaded", function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatHistory = document.getElementById('chat-history');
    const newChatBtn = document.getElementById('new-chat-btn');
    const recentChatsList = document.getElementById('recent-chats-list');

    let currentSessionId = null;

    // --- Event Listeners ---
    chatForm.addEventListener('submit', handleFormSubmit);
    newChatBtn.addEventListener('click', startNewChat);

    /**
     * Handles the submission of the chat form.
     * @param {Event} event - The form submission event.
     */
    async function handleFormSubmit(event) {
        event.preventDefault();
        const userMessage = userInput.value.trim();
        if (userMessage === '') return;

        appendMessage(userMessage, 'user');
        userInput.value = '';
        showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage, session_id: currentSessionId }),
            });

            removeTypingIndicator();

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();
            
            // If it was a new chat, update the session ID and refresh history
            if (!currentSessionId) {
                currentSessionId = data.session_id;
                await loadRecentChats(); // Refresh the list to show the new chat
            }
            
            // Highlight the current chat as active
            setActiveChat(currentSessionId);
            appendMessage(data.response, 'bot');

        } catch (error) {
            console.error('Error fetching chat response:', error);
            removeTypingIndicator();
            appendMessage('Maaf, terjadi kesalahan saat menghubungi server.', 'bot-error');
        }
    }

    /**
     * Appends a message to the chat history container and formats it.
     * @param {string} message - The text content of the message.
     * @param {string} sender - The sender type ('user', 'bot', 'bot-error').
     */
    function appendMessage(message, sender) {
        const messageWrapper = document.createElement('div');
        messageWrapper.className = `chat-message ${sender}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';

        if (sender === 'bot') {
            // First, replace citation markers like [1] with a styled element
            const formattedMessage = message.replace(/\[(\d+)\]/g, '<sup class="citation-marker">$1</sup>');
            // Then, parse the rest of the markdown
            messageContent.innerHTML = marked.parse(formattedMessage);
        } else {
            messageContent.textContent = message;
        }
        
        messageWrapper.appendChild(messageContent);
        chatHistory.appendChild(messageWrapper);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    /**
     * Fetches and displays the list of recent chats in the sidebar.
     */
    async function loadRecentChats() {
        try {
            const response = await fetch('/api/history');
            const chats = await response.json();
            recentChatsList.innerHTML = ''; // Clear existing list
            
            chats.forEach(chat => {
                const li = document.createElement('li');
                li.textContent = chat.title;
                li.dataset.sessionId = chat.id;
                li.addEventListener('click', () => loadConversation(chat.id));
                recentChatsList.appendChild(li);
            });
            // After loading, re-apply the active state if a chat is loaded
            if (currentSessionId) {
                setActiveChat(currentSessionId);
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }

    /**
     * Loads a full conversation history into the chat window.
     * @param {string} sessionId - The ID of the conversation to load.
     */
    async function loadConversation(sessionId) {
        try {
            const response = await fetch(`/api/conversation/${sessionId}`);
            if (!response.ok) throw new Error('Conversation not found.');
            
            const conversation = await response.json();
            chatHistory.innerHTML = ''; // Clear current chat view
            currentSessionId = conversation.id;

            conversation.messages.forEach(msg => {
                appendMessage(msg.content, msg.role);
            });
            setActiveChat(sessionId);
        } catch (error) {
            console.error('Error loading conversation:', error);
            appendMessage('Gagal memuat percakapan.', 'bot-error');
        }
    }
    
    /**
     * Resets the chat interface to start a new conversation.
     */
    function startNewChat() {
        currentSessionId = null;
        chatHistory.innerHTML = `
            <div class="chat-message bot-message">
                <div class="message-content">
                    <p>Silakan ajukan pertanyaan baru Anda.</p>
                </div>
            </div>`;
        userInput.focus();
        setActiveChat(null); // Remove active highlight from all chats
    }

    /**
     * Visually marks a chat in the sidebar as active.
     * @param {string|null} sessionId - The ID of the session to mark as active.
     */
    function setActiveChat(sessionId) {
        const chatItems = recentChatsList.querySelectorAll('li');
        chatItems.forEach(item => {
            if (item.dataset.sessionId === sessionId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    // --- Typing Indicator Functions ---
    function showTypingIndicator() {
        const indicator = `<div id="typing-indicator" class="chat-message bot-message">
                               <div class="message-content"><span></span><span></span><span></span></div>
                           </div>`;
        chatHistory.insertAdjacentHTML('beforeend', indicator);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }
    
    // --- Initial Load ---
    loadRecentChats();
});