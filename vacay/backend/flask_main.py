"""
Main Flask application - Controller layer.
Handles routes, request validation, and delegates to service layers.
"""
import os
import logging
from dotenv import load_dotenv
from datetime import date, datetime
from flask import Flask, request, jsonify, redirect, make_response
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

# Import our service layers
import db_service
import vacation_service
from authnz_service import (
    build_login_response,
    exchange_code_for_tokens_from_cookie,
    get_logout_url,
    get_user_from_auth_header,
    init_authnz,
    refresh_token,
)

load_dotenv()

# Logging (stdlib only)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
logger = logging.getLogger(__name__)

# Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001/dashboard")
PORT = int(os.getenv("FLASK_MAIN_PORT"))

# Custom JSON encoder to handle date objects
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

app = Flask(__name__)
app.json = CustomJSONProvider(app)

# Enable CORS for frontend. NOTE: This is for dev / prototyping purposes only. Never do this in prod.
CORS(app, 
     resources={r"/*": {"origins": "http://localhost:3001"}}, 
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     expose_headers=["Content-Type"])

# Initialize database on startup
db_service.init_db()

# Initialize authn/authz service
try:
    init_authnz()
except Exception as e:
    logger.warning("AuthNZ initialization failed", exc_info=True)

# ==================== Authn/Authz Helper Methods ====================

def get_current_user():
    """Extract and validate user info from JWT token."""
    auth_header = request.headers.get("Authorization")
    return get_user_from_auth_header(auth_header)


def require_auth(f):
    """Decorator to require authentication"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        return f(user, *args, **kwargs)
    return decorated_function

# ==================== API ENDPOINTS ====================

@app.route("/")
def root():
    return jsonify({"message": "Vacation Management API"})

# ==================== OAUTH ENDPOINTS ====================

@app.route("/login")
def login():
    """Initiate OAuth login flow with PKCE"""
    cookie_name = os.getenv('COOKIE_NAME', 'pkce_cookie')
    return build_login_response(cookie_name=cookie_name, max_age=600)

@app.route("/auth/callback")
def auth_callback():
    """Handle OAuth callback and exchange code for tokens"""
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Missing authorization code'}), 400
    
    # Extract PKCE details from cookie
    cookie_name = os.getenv('COOKIE_NAME', 'pkce_cookie')
    raw_cookie = request.cookies.get(cookie_name)
    
    if not raw_cookie:
        return jsonify({'status': 'cookie missing'}), 400
    
    # Exchange authorization code for tokens (PKCE handled in auth service)
    jwt_components = exchange_code_for_tokens_from_cookie(code, raw_cookie)
    
    # Redirect to frontend callback page with tokens
    frontend_base = os.getenv('FRONTEND_URL').split('/dashboard')[0]
    redirect_url = f"{frontend_base}/callback.html?access_token={jwt_components.access_token}&refresh_token={jwt_components.refresh_token}"
    
    response = make_response(redirect(redirect_url))
    response.delete_cookie(cookie_name)
    
    return response

@app.route("/testrefresh")
def test_refresh():
    """Test token refresh functionality"""
    token = request.headers.get('Authorization')
    
    if not token:
        return jsonify({'error': 'Authorization header required'}), 400
    
    # Refresh the token
    new_details = refresh_token(token)
    
    return jsonify({
        'accessToken': new_details.access_token,
        'idToken': new_details.id_token,
        'refreshToken': new_details.refresh_token
    })

@app.route("/logout")
def logout():
    """Logout from SSO session"""
    frontend_base = os.getenv('FRONTEND_URL').split('/dashboard')[0]
    redirect_uri = f"{frontend_base}/"
    logout_url = get_logout_url(redirect_uri)
    return redirect(logout_url)

# ==================== EMPLOYEE ENDPOINTS ====================

@app.route("/employees/me")
@require_auth
def get_my_profile(current_user):
    """Get current user's employee profile"""
    employee = vacation_service.get_user_profile(current_user)
    return jsonify(employee)

@app.route("/employees/me", methods=["PUT"])
@require_auth
def update_my_profile(current_user):
    """Update current user's profile"""
    body = request.get_json()
    
    # Update hire_date if provided
    if 'hire_date' in body:
        hire_date = datetime.strptime(body['hire_date'], '%Y-%m-%d').date()
        updated_employee = vacation_service.update_user_hire_date(current_user, hire_date)
        return jsonify(updated_employee)
    
    employee = vacation_service.get_user_profile(current_user)
    return jsonify(employee)

@app.route("/employees/me/balance")
@require_auth
def get_my_balance(current_user):
    """Get current user's vacation balance"""
    balance = vacation_service.get_user_vacation_balance(current_user)
    
    if balance is None:
        return jsonify({"error": "Employee not found"}), 404
    
    return jsonify(balance)

# ==================== VACATION ENDPOINTS ====================

@app.route("/vacations")
@require_auth
def get_my_vacations(current_user):
    """Get current user's vacation requests"""
    vacations = vacation_service.get_user_vacations(current_user)
    return jsonify(vacations)

@app.route("/vacations", methods=["POST"])
@require_auth
def create_vacation(current_user):
    """Create a new vacation request"""
    body = request.get_json()
    
    start_date = datetime.strptime(body['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(body['end_date'], '%Y-%m-%d').date()
    vacation_type = body['vacation_type']  # 'vacation' or 'optional_holiday'
    notes = body.get('notes', '')
    
    try:
        vacation = vacation_service.create_user_vacation(
            current_user,
            vacation_type,
            start_date,
            end_date,
            notes
        )
        return jsonify(vacation), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/vacations/<int:vacation_id>", methods=["DELETE"])
@require_auth
def delete_vacation(current_user, vacation_id):
    """Delete a vacation request"""
    try:
        vacation_service.delete_user_vacation(current_user, vacation_id)
        return jsonify({"message": "Vacation request deleted successfully"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404 if "not found" in str(e) else 400

# ==================== HOLIDAY ENDPOINTS ====================

@app.route("/holidays")
def get_holidays():
    """Get corporate holidays for a year"""
    year = request.args.get('year', type=int)
    
    # Sync holidays to database
    holidays = vacation_service.sync_holidays_for_year(year)
    return jsonify(holidays)

@app.route("/vacations/calculate-days", methods=["POST"])
def calculate_days():
    """Calculate business days between two dates"""
    body = request.get_json()
    start_date = datetime.strptime(body['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(body['end_date'], '%Y-%m-%d').date()
    
    try:
        result = vacation_service.calculate_business_days_between(start_date, end_date)
        return jsonify({
            "start_date": result["start_date"].isoformat(),
            "end_date": result["end_date"].isoformat(),
            "business_days": result["business_days"],
            "holidays_in_range": [h.isoformat() for h in result["holidays_in_range"]]
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
