# Agentry - MCP Vacation Management Walkthrough

A comprehensive, end-to-end walkthrough demonstrating how to transform a corporate vacation management web application
to support the Model Context Protocol (MCP), enabling integration with an AI-powered chatbot for seamless vacation
management through natural language.

## Overview

This repository contains two interconnected applications that demonstrate MCP integration:

1. **Vacay** - A corporate vacation management web application with both traditional REST API and MCP server interfaces
2. **HR Helper** - An AI-powered chatbot that integrates with the Vacay MCP server to provide conversational vacation management

## Docs

- Main narrative: `docs/WALKTHROUGH.md`
- Article/teaser: `docs/ARTICLE.md`

### Authn/Authz

I have personally found that implementing enterprise-grade code - even prototypes - mandates the implementation of authentication
and authorization ( authn / authz ). Without it, the solution feels incomplete. Accordingly, the applications both rely on OAuth
(OIDC) flows for authentication and authorization. For this example, KeyCloak has been used as the IdP. However, any compliant IdP
should work as well.


## Features

### Vacay Application
- Employee vacation tracking and management
- Vacation day accrual (1 day per month, max 12 per year)
- Optional holiday tracking (3 per year)
- Corporate holiday calculations
- Vacation carryover support (up to 5 days)
- Business day calculations (excluding weekends and holidays)
- OAuth/OIDC authentication with Keycloak
- Dual interface: REST API and MCP server

### HR Helper Chatbot
- Natural language vacation management
- AI-powered assistance using OpenAI (default model: `gpt-4o-mini`)
- MCP protocol integration
- Secure authentication with OAuth/OIDC
- Conversational interface for:
  - Checking vacation balances
  - Creating vacation requests
  - Viewing scheduled time off
  - Calculating business days
  - Querying corporate holidays

## Architecture

```
┌─────────────────┐
│   HR Helper     │  (Flask + OpenAI + MCP Client)
│   Chatbot       │
└────────┬────────┘
         │
         │ MCP over HTTP
         ▼
┌─────────────────┐
│  Vacay MCP      │  (FastMCP + Flask)
│  Server         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │  (Vacation Data)
│   Database      │
└─────────────────┘

┌─────────────────┐
│  Keycloak OIDC  │  (Authentication)
│  Provider       │
└─────────────────┘
```

## Technology Stack

### Backend
- **Python 3.8+**
- **Flask** - Web framework for HR Helper
- **Flask** - Web framework for Vacay REST API
- **FastMCP** - MCP server implementation for Vacay
- **PostgreSQL** - Database for vacation data
- **psycopg2** - PostgreSQL adapter
- **fit-jwt-py** - OAuth/OIDC authentication library
- **OpenAI Chat Completions** - Language model for chatbot (default: `gpt-4o-mini`)

### Frontend
- **Vanilla JavaScript** - Client-side logic
- **HTML5/CSS3** - UI structure and styling
- **OAuth 2.0 + PKCE** - Secure authentication flow

### Protocols
- **MCP (Model Context Protocol)** - For AI tool integration
- **OAuth 2.0 / OIDC** - For authentication
- **REST** - Traditional HTTP API

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Keycloak or compatible OIDC provider
- OpenAI API key
- Access to fit-jwt-py library (from private PyPI server)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd agentry
```

### 2. Set Up Vacay Backend

```bash
cd vacay/backend

# Optional: Create a virtual environment and activate it. (RECOMMENDED)
# Optional: Point to a custom PyPi server. (See pip.conf.sample)

# Install dependencies
pip install -r requirements.txt

# Initialize database + schema
# Note: schema.sql includes CREATE DATABASE and \c commands.
psql -U postgres -f schema.sql

# Optionally, if Postgres is running in a container (container name: mypg):
#
# From this same directory (vacay/backend on the host), you can stream schema.sql into psql
# running inside the container:
#
#   docker exec -i mypg psql -U postgres -v ON_ERROR_STOP=1 -f - < schema.sql
#
# If you prefer to exec into the container first, you can also:
#
#   docker exec -it mypg bash



# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start Flask REST API (optional)
python flask_main.py

```

**NOTE**: As of now, both back-end apps use the same port, so consider running them one at a time.


### 3. Set Up Vacay Frontend

The Vacay frontend is a static site. A simple way to run it locally is to serve it with Python's built-in HTTP server:

Open a new tab, and:

```bash
cd ../frontend
python3 -m http.server 3001
```

**NOTE**: This uses port 3001, which should not conflict with HR Helper (HT Helper defaults to 3000).
If 3001 is already in use, pick another port.

Navigate to http://localhost:3001 and start using the application.

### 4. Set Up HR Helper

**Note:** Stop the prior UI, since they both use the same port.

In the existing back-end terminal, stop the currently running app.
Once stopped, start up the MCP backend:
`python mcp_main.py` (This is instead of `python flask_main.py`)

In (yet another) terminal window:

```bash
cd agentry/hrhelper

# Optional: Create a virtual environment and activate it. (RECOMMENDED)

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key and settings

# Start the chatbot
python server.py
```

Navigate back to http://localhost:3000

### 5. Access the Applications

- **Vacay Frontend**: http://localhost:3001
- **HR Helper Chatbot**: http://localhost:3000
- **Vacay REST API**: http://localhost:8001
- **Vacay MCP Server**: http://localhost:8000/mcp


## Business Rules

### Vacation Accrual
- Employees accrue 1 vacation day per month
- Maximum of 12 vacation days per year
- Accrual starts from hire date

### Vacation Carryover
- Up to 5 unused vacation days can carry over to the next year
- Carryover is calculated automatically

### Optional Holidays
- 3 optional holidays per year
- Cannot be carried over to the next year
- Reset at year boundary

### Corporate Holidays (Excluded from Vacation)
- January 1 (New Year's Day)
- Last Monday in May (Memorial Day)
- July 4 (Independence Day)
- First Monday in September (Labor Day)
- Fourth Thursday in November (Thanksgiving)
- December 25 (Christmas)

### Business Day Calculation
- Excludes weekends (Saturday and Sunday)
- Excludes corporate holidays
- Calculated automatically for vacation requests

## API Endpoints

### Vacay REST API

```
GET    /employees/me               - Get current user profile
PUT    /employees/me               - Update profile (hire_date)
GET    /employees/me/balance       - Get vacation balance
GET    /vacations                  - Get all vacation requests
POST   /vacations                  - Create vacation request
DELETE /vacations/:id              - Delete vacation request
GET    /holidays                   - Get corporate holidays
POST   /vacations/calculate-days   - Calculate business days
POST   /login                      - OAuth login
GET    /auth/callback              - OAuth callback
GET    /logout                     - Logout
```

### MCP Tools (Vacay)

```
get_corporate_holidays(year)                          - Get holidays for a year
get_my_profile()                                      - Get user profile
update_my_profile(hire_date)                          - Update hire date
get_my_balance(year)                                  - Get vacation balance
get_my_vacations()                                    - Get all vacations
create_vacation_entry(type, start, end, notes)        - Create vacation
delete_vacation_entry(id)                             - Delete vacation
calc_business_days(start_date, end_date)              - Calculate business days
```

### HR Helper API

```
GET  /                              - Serve chatbot UI
POST /api/chat                      - Send chat message (authenticated)
GET  /api/tools                     - Get available MCP tools
POST /login                         - OAuth login
GET  /auth/callback                 - OAuth callback
POST /api/auth/refresh              - Refresh JWT token
GET  /api/auth/me                   - Get current user
POST /api/auth/logout               - Logout
```

## MCP Integration Details

### Protocol
- **Transport**: HTTP (StreamableHttp)
- **Version**: 2024-11-05
- **Authentication**: OAuth Bearer tokens passed through

### Flow
1. HR Helper initializes MCP client connection
2. On user authentication, fetches user-specific tools from Vacay MCP server
3. When user sends a chat message:
   - OpenAI receives message + available MCP tools
   - If tool call needed, HR Helper forwards to Vacay MCP server
   - Vacay MCP server validates auth token and executes tool
   - Result returned to OpenAI for natural language response
   - Final response displayed to user

### Security
- All MCP tool calls require valid OAuth access token
- Token validation performed by Vacay MCP server using fit-jwt-py
- User context (employee_id) extracted from token claims
- Authorization enforced at MCP server level


## License

Apache License 2.0 - see LICENSE file for details

## Authors

Created as an educational project demonstrating MCP integration with enterprise applications.

## Acknowledgments

- Model Context Protocol by Anthropic
- FastMCP library by Marvin
- fit-jwt-py for OAuth integration
- OpenAI for the API

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Note**: This is a learning/demonstration application. For production use, additional security hardening, monitoring, and testing are recommended.
