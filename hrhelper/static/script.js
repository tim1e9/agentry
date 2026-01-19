// Chat functionality
const messagesContainer = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const toggleToolsButton = document.getElementById('toggleTools');
const toolsList = document.getElementById('toolsList');

// Authentication elements
const loginButton = document.getElementById('loginButton');
const logoutButton = document.getElementById('logoutButton');
const loginSection = document.getElementById('loginSection');
const userProfile = document.getElementById('userProfile');
const userName = document.getElementById('userName');

// Token storage
let accessToken = localStorage.getItem('accessToken');
let idToken = localStorage.getItem('idToken');
let refreshToken = localStorage.getItem('refreshToken');
let currentUser = null;

// Load available tools on page load
async function loadTools() {
    try {
        const headers = {};
        if (accessToken) {
            headers['Authorization'] = accessToken;
        }

        const response = await fetch('/api/tools', { headers });
        const data = await response.json();
        
        if (data.tools && data.tools.length > 0) {
            toolsList.innerHTML = data.tools.map(tool => `
                <div class="tool-item">
                    <div class="tool-name">${tool.name}</div>
                    <div class="tool-description">${tool.description || 'No description'}</div>
                </div>
            `).join('');
        } else {
            toolsList.innerHTML = '<p style="color: #718096; font-size: 14px;">No tools available</p>';
        }
    } catch (error) {
        console.error('Error loading tools:', error);
        toolsList.innerHTML = '<p style="color: #e53e3e; font-size: 14px;">Error loading tools</p>';
    }
}

// Toggle tools display
toggleToolsButton.addEventListener('click', () => {
    toolsList.classList.toggle('hidden');
    toggleToolsButton.textContent = toolsList.classList.contains('hidden') 
        ? 'Show Available Tools' 
        : 'Hide Available Tools';
});

// Add message to chat
function addMessage(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = isUser ? (currentUser ? currentUser.initials : 'U') : 'HR';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Add loading message
function addLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant loading';
    messageDiv.id = 'loading-message';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'HR';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
    `;
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Remove loading message
function removeLoadingMessage() {
    const loadingMessage = document.getElementById('loading-message');
    if (loadingMessage) {
        loadingMessage.remove();
    }
}

// Send message
async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // Add user message
    addMessage(message, true);
    messageInput.value = '';
    
    // Disable input while processing
    messageInput.disabled = true;
    sendButton.disabled = true;
    
    // Show loading
    addLoadingMessage();
    
    try {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        // Add access token if available
        if (accessToken) {
            headers['Authorization'] = accessToken;
        }
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ message })
        });
        
        const data = await response.json();
        
        removeLoadingMessage();
        
        if (response.ok) {
            addMessage(data.response);
        } else if (response.status === 401) {
            addMessage('Your session has expired. Please login again.');
            logout();
        } else {
            addMessage(`Error: ${data.error || 'Unknown error occurred'}`);
        }
    } catch (error) {
        removeLoadingMessage();
        addMessage(`Error: ${error.message}`);
    } finally {
        messageInput.disabled = false;
        sendButton.disabled = false;
        messageInput.focus();
    }
}

// Event listeners
sendButton.addEventListener('click', sendMessage);

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Authentication functions
function login() {
    window.location.href = '/login';
}

function logout() {
    // Clear server-side session
    fetch('/api/auth/logout', { method: 'POST' }).catch(err => console.error('Logout error:', err));
    
    // Clear client-side tokens
    localStorage.removeItem('accessToken');
    localStorage.removeItem('idToken');
    localStorage.removeItem('refreshToken');
    accessToken = null;
    idToken = null;
    refreshToken = null;
    currentUser = null;
    userName.textContent = '';
    updateAuthUI();
    addMessage('You have been logged out. Please login to continue.');
}

function updateAuthUI() {
    const chatContainer = document.querySelector('.chat-container');
    
    if (accessToken) {
        // User is logged in
        loginSection.classList.add('hidden');
        userProfile.classList.remove('hidden');
        if (chatContainer) chatContainer.style.display = 'flex';
        
        // Extract user info from token (simple base64 decode of payload)
        try {
            const payload = JSON.parse(atob(accessToken.split('.')[1]));
            currentUser = {
                name: payload.name || payload.email || 'User',
                email: payload.email,
                initials: getInitials(payload.name || payload.email || 'U')
            };
            userName.textContent = currentUser.name;
        } catch (e) {
            console.error('Error parsing token:', e);
            currentUser = { name: 'User', initials: 'U' };
            userName.textContent = 'User';
        }
    } else {
        // User is not logged in
        loginSection.classList.remove('hidden');
        userProfile.classList.add('hidden');
        if (chatContainer) chatContainer.style.display = 'none';
        currentUser = null;
        userName.textContent = '';
    }
}

function getInitials(name) {
    if (!name) return 'U';
    const parts = name.split(/[\s@.]+/);
    if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
}

// Handle OAuth callback
function handleAuthCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    
    // Check if we're returning from OAuth callback
    if (urlParams.has('tokens')) {
        // Tokens are in cookies, move them to localStorage
        const cookies = document.cookie.split(';').reduce((acc, cookie) => {
            const [key, value] = cookie.trim().split('=');
            acc[key] = value;
            return acc;
        }, {});
        
        if (cookies.access_token) {
            accessToken = cookies.access_token;
            localStorage.setItem('accessToken', cookies.access_token);
        }
        if (cookies.id_token) {
            idToken = cookies.id_token;
            localStorage.setItem('idToken', cookies.id_token);
        }
        if (cookies.refresh_token) {
            refreshToken = cookies.refresh_token;
            localStorage.setItem('refreshToken', cookies.refresh_token);
        }
        
        // Clear the URL parameter
        window.history.replaceState({}, document.title, window.location.pathname);
        
        // Clear cookies (already in localStorage)
        document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        document.cookie = 'id_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        document.cookie = 'refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        
        updateAuthUI();
        
        // Load tools after successful login
        loadTools();
    }
}

// Event listeners for auth
if (loginButton) {
    loginButton.addEventListener('click', login);
}

if (logoutButton) {
    logoutButton.addEventListener('click', logout);
}

// Initialize
handleAuthCallback();
updateAuthUI();

// Only load tools if user is already authenticated
if (accessToken) {
    loadTools();
    addMessage('Hello! I\'m your HR Helper. I can assist you with vacation requests, time-off balance, and HR policies. How can I help you today?');
} else {
    addMessage('Welcome to HR Helper! Please login to access your HR information and request vacation time.');
}
