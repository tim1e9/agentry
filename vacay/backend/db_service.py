"""
Database service layer for all SQL operations.
Handles connection pooling and raw SQL queries using psycopg2.
"""
import os
from datetime import date
from typing import Dict, Any, List, Optional
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from utils import calculate_vacation_accrued, get_corporate_holidays

load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Database connection pool
pool = None


def init_db():
    """Initialize database connection pool"""
    global pool
    pool = SimpleConnectionPool(1, 20, DATABASE_URL)


def close_db():
    """Close database connection pool"""
    if pool:
        pool.closeall()


def get_connection():
    """Get a connection from the pool"""
    return pool.getconn()


def return_connection(conn):
    """Return a connection to the pool"""
    pool.putconn(conn)


# ==================== YEAR ROLLOVER SERVICE ====================

def ensure_holidays_synced(year: int) -> None:
    """Ensure corporate holidays exist for a given year"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM corporate_holidays WHERE year = %s", (year,))
            count = cur.fetchone()[0]
            
            if count == 0:
                # Sync holidays for this year
                holidays = get_corporate_holidays(year)
                holiday_names = ["New Year's Day", "Memorial Day", "Independence Day", 
                               "Labor Day", "Thanksgiving", "Christmas"]
                
                for i, holiday_date in enumerate(holidays):
                    cur.execute("""
                        INSERT INTO corporate_holidays (name, holiday_date, year)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (holiday_date) DO NOTHING
                    """, (holiday_names[i], holiday_date, year))
                
                conn.commit()
    finally:
        return_connection(conn)


def check_and_handle_year_rollover(employee_id: int) -> None:
    """
    Check if we need to handle year rollover for this employee.
    This runs lazily when the user accesses their balance.
    
    Year rollover logic:
    - Ensure current year holidays are synced
    - Vacation days reset to 0 used (accrual is calculated fresh each year)
    - Up to 5 days can carry over from previous year
    - Optional holidays reset to 0 (no carryover)
    """
    current_year = date.today().year
    
    # Always ensure holidays are synced for current and next year
    ensure_holidays_synced(current_year)
    ensure_holidays_synced(current_year + 1)
    
    # Note: We don't need to "reset" anything because:
    # - Vacation accrual is calculated on-the-fly based on hire_date
    # - Carryover is calculated by looking at previous year's usage
    # - The get_vacation_balance() function already handles all this logic
    # 
    # This function simply ensures holidays are available for calculations


# ==================== EMPLOYEE OPERATIONS ====================

def get_or_create_employee(user_info: Dict[str, Any]) -> Dict[str, Any]:
    """Get or create employee from JWT user info"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Try to find existing employee
            cur.execute(
                "SELECT * FROM employees WHERE oidc_user_id = %s",
                (user_info['oidc_user_id'],)
            )
            employee = cur.fetchone()
            
            if employee:
                return dict(employee)
            
            # Create new employee
            cur.execute("""
                INSERT INTO employees (oidc_user_id, email, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            """, (user_info['oidc_user_id'], user_info['email'], 
                user_info['first_name'], user_info['last_name']))
            
            employee = cur.fetchone()
            conn.commit()
            
            return dict(employee)
    finally:
        return_connection(conn)


def update_employee_hire_date(employee_id: int, hire_date: date) -> Dict[str, Any]:
    """Update employee's hire date"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "UPDATE employees SET hire_date = %s WHERE id = %s",
                (hire_date, employee_id)
            )
            conn.commit()
            
            cur.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
            employee = cur.fetchone()
            return dict(employee)
    finally:
        return_connection(conn)


def get_employee_by_id(employee_id: int) -> Optional[Dict[str, Any]]:
    """Get employee by ID"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
            employee = cur.fetchone()
            return dict(employee) if employee else None
    finally:
        return_connection(conn)


# ==================== VACATION OPERATIONS ====================

def get_vacation_balance(employee_id: int, year: int = None) -> Dict[str, Any]:
    """Calculate current vacation balance for employee"""
    if year is None:
        year = date.today().year
    
    # Ensure holidays are synced for current year (lazy initialization)
    check_and_handle_year_rollover(employee_id)
    
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get employee info
            cur.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
            employee = cur.fetchone()
            if not employee:
                return None
            
            # Calculate accrued vacation days for the current year
            # Each year, employee accrues 1 day per month (max 12)
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)
            
            # If hired this year, calculate from hire date
            if employee['hire_date'].year == year:
                accrual_start = employee['hire_date']
            else:
                accrual_start = year_start
            
            # Calculate months worked in this year so far
            current = date.today()
            accrual_end = min(current, year_end)
            
            if accrual_start <= accrual_end:
                months_worked = (accrual_end.year - accrual_start.year) * 12 + accrual_end.month - accrual_start.month
                if accrual_end.day >= accrual_start.day:
                    months_worked += 1
                accrued = min(12, max(0, months_worked))
            else:
                accrued = 0
            
            # Get used vacation days for this year
            cur.execute("""
                SELECT COALESCE(SUM(business_days), 0) as total
                FROM vacation_requests
                WHERE employee_id = %s AND vacation_type = 'vacation' 
                AND EXTRACT(YEAR FROM start_date) = %s AND status = 'approved'
            """, (employee_id, year))
            vacation_used = cur.fetchone()['total']
            
            # Get used optional holidays for this year
            cur.execute("""
                SELECT COALESCE(SUM(business_days), 0) as total
                FROM vacation_requests
                WHERE employee_id = %s AND vacation_type = 'optional_holiday'
                AND EXTRACT(YEAR FROM start_date) = %s AND status = 'approved'
            """, (employee_id, year))
            holidays_used = cur.fetchone()['total']
            
            # Calculate carryover (max 5 days from previous year)
            carryover = 0
            if year > employee['hire_date'].year:
                prev_year_accrued = min(12, calculate_vacation_accrued(employee['hire_date'], date(year-1, 12, 31)))
                cur.execute("""
                    SELECT COALESCE(SUM(business_days), 0) as total
                    FROM vacation_requests
                    WHERE employee_id = %s AND vacation_type = 'vacation'
                    AND EXTRACT(YEAR FROM start_date) = %s AND status = 'approved'
                """, (employee_id, year-1))
                prev_year_used = cur.fetchone()['total'] or 0
                
                carryover = min(5, max(0, prev_year_accrued - prev_year_used))
            
            return {
                'vacation_accrued': min(12, accrued),  # Max 12 per year
                'vacation_used': vacation_used or 0,
                'vacation_available': min(12, accrued) + carryover - (vacation_used or 0),
                'vacation_carryover': carryover,
                'optional_holidays_used': holidays_used or 0,
                'optional_holidays_available': 3 - (holidays_used or 0)
            }
    finally:
        return_connection(conn)


def get_vacations_for_employee(employee_id: int) -> List[Dict[str, Any]]:
    """Get all vacation requests for an employee"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM vacation_requests 
                WHERE employee_id = %s 
                ORDER BY start_date DESC
            """, (employee_id,))
            
            vacations = cur.fetchall()
            return [dict(v) for v in vacations]
    finally:
        return_connection(conn)


def create_vacation_request(
    employee_id: int,
    vacation_type: str,
    start_date: date,
    end_date: date,
    business_days: int,
    notes: str = ""
) -> Dict[str, Any]:
    """Create a new vacation request"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO vacation_requests (employee_id, vacation_type, start_date, end_date, business_days, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (employee_id, vacation_type, start_date, end_date, business_days, notes))
            
            vacation = cur.fetchone()
            conn.commit()
            
            return dict(vacation)
    finally:
        return_connection(conn)


def get_vacation_by_id(vacation_id: int, employee_id: int) -> Optional[Dict[str, Any]]:
    """Get vacation request by ID for a specific employee"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM vacation_requests WHERE id = %s AND employee_id = %s
            """, (vacation_id, employee_id))
            
            vacation = cur.fetchone()
            return dict(vacation) if vacation else None
    finally:
        return_connection(conn)


def delete_vacation_request(vacation_id: int) -> None:
    """Delete a vacation request"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM vacation_requests WHERE id = %s", (vacation_id,))
            conn.commit()
    finally:
        return_connection(conn)


# ==================== HOLIDAY OPERATIONS ====================

def sync_holidays_to_db(year: int) -> List[Dict[str, Any]]:
    """Sync corporate holidays to database for a given year"""
    holidays = get_corporate_holidays(year)
    holiday_names = ["New Year's Day", "Memorial Day", "Independence Day", "Labor Day", "Thanksgiving", "Christmas"]
    
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Clear existing holidays for the year
            cur.execute("DELETE FROM corporate_holidays WHERE year = %s", (year,))
            
            # Insert calculated holidays
            for i, holiday_date in enumerate(holidays):
                cur.execute("""
                    INSERT INTO corporate_holidays (name, holiday_date, year)
                    VALUES (%s, %s, %s)
                """, (holiday_names[i], holiday_date, year))
            
            conn.commit()
            
            # Return holidays
            cur.execute("SELECT * FROM corporate_holidays WHERE year = %s ORDER BY holiday_date", (year,))
            db_holidays = cur.fetchall()
            return [dict(h) for h in db_holidays]
    finally:
        return_connection(conn)
