"""
Business logic layer for vacation management.
This service layer contains all business rules and orchestrates between db_service and utils.
"""

from datetime import date, datetime
from typing import Dict, Any, List, Optional
import db_service
from utils import calculate_business_days, get_corporate_holidays


# ==================== USER/EMPLOYEE OPERATIONS ====================

def get_user_profile(user_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get or create employee profile from user info.
    
    Args:
        user_info: Dictionary containing user info from JWT (oidc_user_id, email, etc)
    
    Returns:
        Employee profile dictionary
    """
    employee = db_service.get_or_create_employee(user_info)
    return employee


def update_user_hire_date(user_info: Dict[str, Any], hire_date: date) -> Dict[str, Any]:
    """
    Update user's hire date.
    
    Args:
        user_info: Dictionary containing user info from JWT
        hire_date: New hire date
    
    Returns:
        Updated employee profile
    """
    employee = db_service.get_or_create_employee(user_info)
    updated_employee = db_service.update_employee_hire_date(employee['id'], hire_date)
    return updated_employee


def get_user_vacation_balance(user_info: Dict[str, Any], year: int = None) -> Dict[str, Any]:
    """
    Get user's vacation balance for a given year.
    
    Args:
        user_info: Dictionary containing user info from JWT
        year: Year to check balance for (defaults to current year)
    
    Returns:
        Dictionary with vacation balance details
    """
    if year is None:
        year = date.today().year
    
    employee = db_service.get_or_create_employee(user_info)
    balance = db_service.get_vacation_balance(employee['id'], year)
    return balance


# ==================== VACATION OPERATIONS ====================

def get_user_vacations(user_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all vacation requests for a user.
    
    Args:
        user_info: Dictionary containing user info from JWT
    
    Returns:
        List of vacation request dictionaries
    """
    employee = db_service.get_or_create_employee(user_info)
    vacations = db_service.get_vacations_for_employee(employee['id'])
    return vacations


def create_user_vacation(
    user_info: Dict[str, Any],
    vacation_type: str,
    start_date: date,
    end_date: date,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Create a new vacation request for a user with validation.
    
    Args:
        user_info: Dictionary containing user info from JWT
        vacation_type: Type of vacation ('vacation' or 'optional_holiday')
        start_date: Start date of vacation
        end_date: End date of vacation
        notes: Optional notes
    
    Returns:
        Created vacation request dictionary
    
    Raises:
        ValueError: If validation fails
    """
    employee = db_service.get_or_create_employee(user_info)
    
    # Validate dates
    if start_date > end_date:
        raise ValueError("Start date must be before end date")
    
    if start_date < date.today():
        raise ValueError("Cannot schedule vacation in the past")
    
    # Get holidays for the year(s)
    holidays = []
    for year in range(start_date.year, end_date.year + 1):
        holidays.extend(get_corporate_holidays(year))
    
    # Calculate business days
    business_days = calculate_business_days(start_date, end_date, holidays)
    
    if business_days == 0:
        raise ValueError("No business days in selected date range")
    
    # Check vacation balance
    balance = db_service.get_vacation_balance(employee['id'], start_date.year)
    
    if vacation_type == 'vacation':
        if business_days > balance['vacation_available']:
            raise ValueError(
                f"Insufficient vacation days. Available: {balance['vacation_available']}, Requested: {business_days}"
            )
    elif vacation_type == 'optional_holiday':
        if business_days > balance['optional_holidays_available']:
            raise ValueError(
                f"Insufficient optional holidays. Available: {balance['optional_holidays_available']}, Requested: {business_days}"
            )
    
    # Create vacation request
    vacation = db_service.create_vacation_request(
        employee['id'],
        vacation_type,
        start_date,
        end_date,
        business_days,
        notes
    )
    
    return vacation


def delete_user_vacation(user_info: Dict[str, Any], vacation_id: int) -> None:
    """
    Delete a user's vacation request with validation.
    
    Args:
        user_info: Dictionary containing user info from JWT
        vacation_id: ID of vacation to delete
    
    Raises:
        ValueError: If vacation not found or validation fails
    """
    employee = db_service.get_or_create_employee(user_info)
    
    # Get vacation to check ownership and dates
    print(f"DEBUG: Employee: {str(employee)}. Vacation ID: {vacation_id}")
    vacation = db_service.get_vacation_by_id(vacation_id, employee['id'])
    
    if not vacation:
        raise ValueError("Vacation request not found")
    
    if vacation['start_date'] < date.today():
        raise ValueError("Cannot delete past vacation requests")
    
    # Delete vacation
    db_service.delete_vacation_request(vacation_id)


# ==================== HOLIDAY OPERATIONS ====================

def get_holidays_for_year(year: int = None) -> List[Dict[str, Any]]:
    """
    Get corporate holidays for a given year.
    
    Args:
        year: Year to get holidays for (defaults to current year)
    
    Returns:
        List of holiday dictionaries with name and date
    """
    if year is None:
        year = date.today().year
    
    holidays = get_corporate_holidays(year)
    holiday_names = ["New Year's Day", "Memorial Day", "Independence Day", 
                    "Labor Day", "Thanksgiving", "Christmas"]
    
    return [
        {"name": holiday_names[i], "date": h}
        for i, h in enumerate(holidays)
    ]


def sync_holidays_for_year(year: int = None) -> List[Dict[str, Any]]:
    """
    Sync corporate holidays to database for a given year.
    
    Args:
        year: Year to sync holidays for (defaults to current year)
    
    Returns:
        List of synced holiday dictionaries from database
    """
    if year is None:
        year = date.today().year
    
    holidays = db_service.sync_holidays_to_db(year)
    return holidays


def calculate_business_days_between(
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """
    Calculate business days between two dates with holiday information.
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        Dictionary with business_days count and holidays in range
    
    Raises:
        ValueError: If start_date is after end_date
    """
    if start_date > end_date:
        raise ValueError("Start date must be before end date")
    
    # Get holidays for the year(s)
    holidays = []
    for year in range(start_date.year, end_date.year + 1):
        holidays.extend(get_corporate_holidays(year))
    
    business_days = calculate_business_days(start_date, end_date, holidays)
    holidays_in_range = [h for h in holidays if start_date <= h <= end_date]
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "business_days": business_days,
        "holidays_in_range": holidays_in_range
    }
