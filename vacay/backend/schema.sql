-- Vacation Management Database Schema
-- 
-- Design Philosophy:
-- - Vacation accrual is CALCULATED on-the-fly based on hire_date (not stored)
-- - This ensures accuracy and eliminates the need for batch jobs
-- - Corporate holidays are lazily synced when users access their balance
-- - Year rollover happens automatically when balance is checked
--

-- Create database
CREATE DATABASE vacay_db;

-- Connect to the database
\c vacay_db;

CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    oidc_user_id VARCHAR UNIQUE NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    hire_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vacation_requests (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    vacation_type VARCHAR CHECK (vacation_type IN ('vacation', 'optional_holiday')) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    business_days INTEGER NOT NULL,
    notes TEXT,
    status VARCHAR DEFAULT 'approved' CHECK (status IN ('approved', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS corporate_holidays (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    holiday_date DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL
);

-- Index for better performance
CREATE INDEX IF NOT EXISTS idx_vacation_requests_employee ON vacation_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_vacation_requests_dates ON vacation_requests(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_holidays_date ON corporate_holidays(holiday_date);