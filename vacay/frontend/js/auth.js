// Authentication module using OAuth with PKCE flow
// Handles login, token storage, and user session management

const API_BASE = 'http://localhost:8001'; // TODO: Remove anything hard-coded. (Fine for prototyping, but don't forget!)
const TOKEN_KEY = 'vacay_access_token';
const REFRESH_TOKEN_KEY = 'vacay_refresh_token';
const USER_KEY = 'vacay_user';

export class Auth {
    static getToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    static setToken(accessToken, refreshToken) {
        localStorage.setItem(TOKEN_KEY, accessToken);
        if (refreshToken) {
            localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
        }
    }

    static clearTokens() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }

    static getUser() {
        const userJson = localStorage.getItem(USER_KEY);
        return userJson ? JSON.parse(userJson) : null;
    }

    static setUser(user) {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    static isAuthenticated() {
        return !!this.getToken();
    }

    static async login() {
        // Redirect to backend login endpoint which will handle OAuth flow
        window.location.href = `${API_BASE}/login`;
    }

    static logout() {
        this.clearTokens();
        // Redirect to backend logout endpoint which will clear Keycloak SSO session
        window.location.href = `${API_BASE}/logout`;
    }

    static async handleCallback() {
        // This is called from the OAuth callback page
        // The backend should have set the token in the response
        const urlParams = new URLSearchParams(window.location.search);
        const error = urlParams.get('error');
        
        if (error) {
            console.error('OAuth error:', error);
            return false;
        }

        // Check if we have a token (backend should redirect with token or handle it)
        return this.isAuthenticated();
    }

    static async refreshToken() {
        const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
        if (!refreshToken) {
            return false;
        }

        try {
            const response = await fetch(`${API_BASE}/testrefresh`, {
                headers: {
                    'Authorization': refreshToken
                }
            });

            if (!response.ok) {
                this.clearTokens();
                return false;
            }

            const data = await response.json();
            this.setToken(data.accessToken, data.refreshToken);
            return true;
        } catch (error) {
            console.error('Token refresh failed:', error);
            this.clearTokens();
            return false;
        }
    }

    static getAuthHeaders() {
        const token = this.getToken();
        return token ? {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        } : {
            'Content-Type': 'application/json'
        };
    }
}
