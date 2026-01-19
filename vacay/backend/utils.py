"""
Utility functions for business logic calculations.
Pure functions with no database dependencies.
"""
from datetime import date, timedelta
from typing import List


def calculate_business_days(start_date: date, end_date: date, holidays: List[date]) -> int:
    """Calculate business days between two dates, excluding weekends and holidays"""
    if start_date > end_date:
        return 0
    
    total_days = 0
    current = start_date
    
    while current <= end_date:
        # Skip weekends (Saturday=5, Sunday=6)
        if current.weekday() < 5 and current not in holidays:
            total_days += 1
        current += timedelta(days=1)
    
    return total_days


def get_corporate_holidays(year: int) -> List[date]:
    """Calculate corporate holidays for a given year"""
    holidays = []
    
    # Fixed date holidays
    holidays.append(date(year, 1, 1))   # New Year's Day
    holidays.append(date(year, 7, 4))   # Independence Day
    holidays.append(date(year, 12, 25)) # Christmas
    
    # Memorial Day (last Monday in May)
    may_last = date(year, 5, 31)
    memorial_day = may_last - timedelta(days=(may_last.weekday() + 1) % 7)
    holidays.append(memorial_day)
    
    # Labor Day (first Monday in September)
    sept_first = date(year, 9, 1)
    labor_day = sept_first + timedelta(days=(7 - sept_first.weekday()) % 7)
    holidays.append(labor_day)
    
    # Thanksgiving (fourth Thursday in November)
    nov_first = date(year, 11, 1)
    # Find first Thursday
    first_thursday = nov_first + timedelta(days=(3 - nov_first.weekday()) % 7)
    thanksgiving = first_thursday + timedelta(weeks=3)
    holidays.append(thanksgiving)
    
    return holidays


def calculate_vacation_accrued(hire_date: date, current_date: date = None) -> int:
    """Calculate vacation days accrued (1 per month)"""
    if current_date is None:
        current_date = date.today()
    
    if hire_date > current_date:
        return 0
    
    # Calculate complete months
    months = (current_date.year - hire_date.year) * 12 + current_date.month - hire_date.month
    if current_date.day < hire_date.day:
        months -= 1
    
    return max(0, months)
