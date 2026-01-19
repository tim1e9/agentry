#!/usr/bin/env python3
"""
MCP interface for vacation functionality with StreamableHttp transport.
Secured with OAuth/OIDC token validation using fit-jwt-py.
This is a thin wrapper around the vacation service, suitable for remote/enterprise deployment.
"""

import os
import logging
from dotenv import load_dotenv
from datetime import date, datetime
from pydantic import AnyHttpUrl
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token

import db_service
import vacation_service
from authnz_service import init_authnz, get_user_from_token
from token_verifier import create_token_verifier_from_env

# Load environment variables from .env file
load_dotenv()

# Logging (stdlib only)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
logger = logging.getLogger(__name__)

# Initialize fitjwtpy if OAuth environment variables are present
# This loads JWKS keys and validates configuration
token_verifier = None
auth_settings = None

if all([os.getenv("JWKS_URL"), os.getenv("OAUTH_ISSUER"), os.getenv("OAUTH_AUDIENCE"), os.getenv("CLIENT_ID")]):
    try:
        
        # Initialize authn/authz service - loads environment variables and fetches JWKS
        init_authnz()
        logger.info("AuthNZ initialized successfully")
        
        # Create token verifier from environment variables
        token_verifier = create_token_verifier_from_env()
        
        # Configure OAuth settings
        auth_settings = AuthSettings(
            issuer_url=AnyHttpUrl(os.getenv("OAUTH_ISSUER")),
            resource_server_url=AnyHttpUrl(os.getenv("OAUTH_RESOURCE_URL")),
            required_scopes=[]
        )
    except Exception as e:
        logger.warning("Failed to initialize OAuth", exc_info=True)
else:
    logger.warning(
        "Running without authentication (set JWKS_URL, OAUTH_ISSUER, OAUTH_AUDIENCE, CLIENT_ID to enable)"
    )

# Create MCP server instance with JSON responses and optional OAuth
mcp = FastMCP(
    "Vacation",
    json_response=True,
    token_verifier=token_verifier,
    auth=auth_settings
)

# Initialize database connection pool
db_service.init_db()


# ==================== HELPER FUNCTIONS ====================

def get_current_user_from_mcp():
    """Extract user info from MCP authentication context"""
    access_token = get_access_token()
    if not access_token:
        raise ValueError("Not authenticated")
    
    # Use authn/authz service to extract user info from token
    user_info = get_user_from_token(access_token.token)
    if not user_info:
        raise ValueError("Invalid or expired token")
    
    return user_info


# ==================== MCP TOOLS ====================

@mcp.tool()
def get_corporate_holidays(year: int = None) -> list:
    """
    Get the list of corporate holidays for a given year.
    
    Args:
        year: The year to get holidays for (defaults to current year)
    
    Returns:
        List of holidays with name and date
    """
    holidays = vacation_service.get_holidays_for_year(year)
    # Convert dates to ISO format strings
    return [
        {"name": h["name"], "date": h["date"].isoformat()}
        for h in holidays
    ]


@mcp.tool()
def get_my_profile() -> dict:
    """
    Get information about the current authenticated user.
    
    Returns:
        User profile including employee information
    """
    try:
        current_user = get_current_user_from_mcp()
        employee = vacation_service.get_user_profile(current_user)
        
        # Convert date to ISO format if present
        if employee.get('hire_date'):
            employee['hire_date'] = employee['hire_date'].isoformat()
        
        return employee
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def update_my_profile(hire_date: str) -> dict:
    """
    Update the current user's profile.
    
    Args:
        hire_date: Hire date in YYYY-MM-DD format
    
    Returns:
        Updated employee profile
    """
    try:
        current_user = get_current_user_from_mcp()
        hire_date_obj = date.fromisoformat(hire_date)
        
        updated_employee = vacation_service.update_user_hire_date(current_user, hire_date_obj)
        
        # Convert date to ISO format
        if updated_employee.get('hire_date'):
            updated_employee['hire_date'] = updated_employee['hire_date'].isoformat()
        
        return updated_employee
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def get_my_balance(year: int = None) -> dict:
    """
    Get the authenticated user's vacation balance.
    
    Args:
        year: The year to check balance for (defaults to current year)
    
    Returns:
        Vacation balance including accrued, used, and available days
    """
    try:
        current_user = get_current_user_from_mcp()
        balance = vacation_service.get_user_vacation_balance(current_user, year)
        
        if balance is None:
            return {"error": "Employee not found"}
        
        return balance
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def get_my_vacations() -> list:
    """
    Get all vacation requests for the current user.
    
    Returns:
        List of vacation requests with details
    """
    try:
        current_user = get_current_user_from_mcp()
        vacations = vacation_service.get_user_vacations(current_user)
        
        # Convert dates to ISO format
        for v in vacations:
            if v.get('start_date'):
                v['start_date'] = v['start_date'].isoformat()
            if v.get('end_date'):
                v['end_date'] = v['end_date'].isoformat()
            if v.get('created_at'):
                v['created_at'] = v['created_at'].isoformat()
        
        return vacations
    except ValueError as e:
        return [{"error": str(e)}]


@mcp.tool()
def create_vacation_entry(vacation_type: str, start_date: str, end_date: str, notes: str = "") -> dict:
    """
    Create a new vacation entry for the current user.
    
    Args:
        vacation_type: Type of vacation ('vacation' or 'optional_holiday')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        notes: Optional notes about the vacation
    
    Returns:
        The created vacation entry
    """
    try:
        current_user = get_current_user_from_mcp()
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        
        vacation = vacation_service.create_user_vacation(
            current_user,
            vacation_type,
            start,
            end,
            notes
        )
        
        # Convert dates to ISO format
        if vacation.get('start_date'):
            vacation['start_date'] = vacation['start_date'].isoformat()
        if vacation.get('end_date'):
            vacation['end_date'] = vacation['end_date'].isoformat()
        if vacation.get('created_at'):
            vacation['created_at'] = vacation['created_at'].isoformat()
        
        return vacation
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def delete_vacation_entry(vacation_id: int) -> dict:
    """
    Delete a vacation entry for the current user.
    
    Args:
        vacation_id: The ID of the vacation entry to delete
    
    Returns:
        Confirmation message
    """
    print("Candy is tasty.")
    try:
        print(f"I like Van Halen. The vacation ID is: {vacation_id}")
        current_user = get_current_user_from_mcp()
        print(f"The current user is: {str(current_user)}")
        vacation_service.delete_user_vacation(current_user, vacation_id)
        print("Yes I do")
        return {"message": "Vacation request deleted successfully"}
    except ValueError as e:
        print(f"Yo, I got an error: {str(e)}")
        return {"error": str(e)}


@mcp.tool()
def calc_business_days(start_date: str, end_date: str) -> dict:
    """
    Calculate the number of business days between two dates.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    
    Returns:
        Dictionary with business days count and holidays in range
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        
        result = vacation_service.calculate_business_days_between(start, end)
        
        # Convert dates to ISO format
        return {
            "start_date": result["start_date"].isoformat(),
            "end_date": result["end_date"].isoformat(),
            "business_days": result["business_days"],
            "holidays_in_range": [h.isoformat() for h in result["holidays_in_range"]]
        }
    except ValueError as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Run with StreamableHttp transport
    mcp.run(transport="streamable-http")