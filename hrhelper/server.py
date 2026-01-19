"""
Flask backend server for HR Helper with OAuth authentication.
"""
from flask import Flask, request, jsonify, send_from_directory, redirect, make_response, session
import os
import logging
from dotenv import load_dotenv
import json
from functools import wraps

from chat_service import ChatService

from fitjwtpy import (
    init as fitjwt_init,
    get_auth_url,
    get_pkce_details,
    get_jwt_token,
    is_token_valid,
    refresh_jwt_token,
    get_user_from_token
)

# Load environment variables
load_dotenv()

# Logging (stdlib only)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))  # For session management

chattie = ChatService()

# Cookie configuration
COOKIE_NAME = os.getenv('COOKIE_NAME', 'vacay_auth_token')
JWT_HEADER_NAME = os.getenv('JWT_HEADER_NAME', 'Authorization')

def require_auth(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_token = request.headers.get(JWT_HEADER_NAME)
        if not access_token:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = get_user_from_token(access_token)
        if not user:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Attach user to request object
        request.user = user
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """Serve the main page."""
    return send_from_directory('static', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files."""
    return send_from_directory('static', path)


# OAuth Authentication Endpoints

@app.route('/login')
def login():
    """Redirect to OAuth provider with PKCE."""
    pkce_details = get_pkce_details('S256')
    response = make_response(redirect(get_auth_url(pkce_details)))
    response.set_cookie(COOKIE_NAME, json.dumps({
        'codeVerifier': pkce_details.code_verifier,
        'codeChallenge': pkce_details.code_challenge,
        'method': pkce_details.method
    }), httponly=True, samesite='Lax')
    return response


@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback and exchange code for tokens."""
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'No authorization code provided'}), 400
        
        # Extract PKCE details from cookie
        raw_cookie = request.cookies.get(COOKIE_NAME)
        if not raw_cookie:
            return jsonify({'error': 'Missing PKCE cookie'}), 400
        
        pkce_details = json.loads(raw_cookie)
        
        # Exchange code for tokens
        jwt_components = get_jwt_token(code, pkce_details['codeVerifier'])
        
        # Validate the ID token
        is_token_valid(jwt_components.id_token, "id_token")
        
        # Get frontend URL for redirect
        frontend_url = os.getenv('FRONTEND_URL')
        
        # Create response with redirect to frontend
        response = make_response(redirect(f"{frontend_url}?tokens=true"))
        
        # Clear PKCE cookie
        response.set_cookie(COOKIE_NAME, '', expires=0)
        
        # Set tokens in cookies for client-side storage
        # Note: httpOnly=False allows JavaScript access for localStorage
        response.set_cookie('access_token', jwt_components.access_token, httponly=False, samesite='Lax')
        response.set_cookie('id_token', jwt_components.id_token, httponly=False, samesite='Lax')
        response.set_cookie('refresh_token', jwt_components.refresh_token, httponly=False, samesite='Lax')
        
        return response
        
    except Exception as e:
        logger.exception("Error in OAuth callback")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/refresh', methods=['POST'])
def refresh():
    """Refresh JWT token."""
    try:
        token = request.headers.get(JWT_HEADER_NAME)
        if not token:
            return jsonify({'error': 'No refresh token provided'}), 400
        
        new_tokens = refresh_jwt_token(token)
        
        return jsonify({
            'accessToken': new_tokens.access_token,
            'idToken': new_tokens.id_token,
            'refreshToken': new_tokens.refresh_token
        })
        
    except Exception as e:
        logger.exception("Error refreshing token")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current authenticated user info."""
    return jsonify({'user': request.user})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Clear server-side session on logout."""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


# Chat Endpoint (Protected)

@app.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    """Handle chat messages."""
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get user from request (set by @require_auth decorator)
        user = request.user
        employee_id = user.get('sub') or user.get('email') or user.get('preferred_username')
        
        # Get access token to potentially pass to MCP server
        access_token = request.headers.get(JWT_HEADER_NAME)

        # Fetch user-specific tools from MCP server (with session caching)
        # These are obviously user-specific, so keep them in the session
        if 'user_tools' not in session:
            session['user_tools'] = chattie.get_tools(access_token=access_token)

        user_tools = session['user_tools']

        # Initialize conversation history in session if not exists
        # Again - user-specific, so keep in the session.
        # Consider persistence in a DB if this gets too big or we need multiple instances
        if 'conversation_history' not in session:
            session['conversation_history'] = [
                {
                    "role": "system",
                    "content": chattie.get_initial_prompt()
                }
            ]
        
        # Add current user message to conversation history
        session['conversation_history'].append({
            "role": "user",
            "content": user_message
        })
        
        # Use conversation history for messages
        messages = session['conversation_history'].copy()

        updated_messages = chattie.chat(employee_id=employee_id, user_tools=user_tools,
                              messages=messages, access_token=access_token)
        
        
        # Add assistant response to conversation history
        session['conversation_history'].extend(updated_messages)
        session.modified = True  # Mark session as modified to ensure it's saved
        
        return jsonify({
            'response': updated_messages[-1]['content']
        })
        
    except Exception as e:
        logger.exception("Error in chat endpoint")
        return jsonify({'error': str(e)}), 500



@app.route('/api/tools', methods=['GET'])
@require_auth
def get_tools():
    """Get list of available tools for the authenticated user."""
    access_token = request.headers.get(JWT_HEADER_NAME)
    # Forward the user's access token to the MCP server to get user-specific tools
    tools = chattie.get_tools(access_token=access_token)
    return jsonify({'tools': tools})


if __name__ == '__main__':
    # Initialize fitjwtpy with OAuth configuration
    logger.info("Initializing fitjwtpy...")
    try:
        fitjwt_init()
        logger.info("fitjwtpy initialized successfully")
    except Exception as e:
        logger.warning("fitjwtpy initialization failed; OAuth authentication will not work until configuration is fixed", exc_info=True)
    
    
    # Start server
    logger.info("Starting Flask server...")
    app.run(debug=True, port=3000)
