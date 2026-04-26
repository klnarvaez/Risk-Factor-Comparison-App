# Risk Factor Comparison App — Web Application

This repository contains a web application for comparing risk factors of companies. Users can register, log in, and request risk assessments for companies using AI-powered analysis. The application uses a SQL database for robust data storage and includes an administrator interface for database management.

## Features

- **User Authentication**: Secure user registration and login system
- **Company Risk Analysis**: AI-powered risk factor extraction across 5 categories (Strategic, Financial, Legal, Operational, Technology)
- **User-Associated Data**: Each user only sees companies and risks they have requested

## Changelog

### 2026-03-29
- Added custom admin dashboard at `/admin/dashboard` with direct links for Users, Companies, Risks, and Associations
- Implemented admin-only access using an `admin_required` decorator (active for `kristina@erm-strategies.com`)
- Added user merge functionality (consolidate or archive accounts) via `/admin/merge-users`
- Added admin management UI templates in `templates/admin/*`
- Added delete action in Users list table plus in-user detail deletion
- Updated main app admin button to link to `/admin/dashboard`
- Added dynamic `admin_user_detail` route accepting either numeric user ID or UUID user_id (`/admin/users/<user_key>`)
- Fixed dashboard CSS block injection to correctly apply `.dashboard-card` styling (moved child `{% block extra_css %}` outside `<style>` in base template)
- **Timestamp Tracking**: Records when users request company risk data
- **Web Interface**: Clean, responsive web UI built with Flask and Jinja2 templates
- **Jinja2 Templating**: Dynamic HTML rendering with proper separation of concerns between backend logic and frontend presentation
- **LLM Integration**: Supports both mock mode and OpenAI API for risk analysis
- **SQL Database Storage**: Robust data persistence using SQLAlchemy with SQLite (development) and PostgreSQL (production)
- **Administrator Interface**: Flask-Admin interface for database management (admin user only)
- **Heroku Ready**: Configured for deployment on Heroku with PostgreSQL database

## Quick Start Guide

This guide covers setting up the application for development, testing, and production deployment to Heroku.

### Prerequisites
- Python 3.11 or higher
- Git (for version control)
- Heroku CLI (for deployment)

### Local Development Setup

1. **Clone or navigate to the repository** (if not already done):
   ```powershell
   cd "C:\Users\krist_9fwbed0\OneDrive\UVU\Courses\Info 6200\Projects\Risk Factor Comparison App"
   ```

2. **Create and activate a Python virtual environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - Copy `.env.example` to `.env`:
     ```powershell
     cp .env.example .env
     ```
   - Edit `.env` with your configuration (see Configuration section below)

5. **Run security setup** (generates secure Flask secret key):
   ```powershell
   python security_setup.py
   ```
   Follow the prompts to set up your environment.

6. **Run the application locally** (database tables will be created automatically):
   ```powershell
   python web_app.py
   ```
   - Open your browser to `http://localhost:5000`
   - Register a new account or log in

### Testing

1. **Run unit tests**:
   ```powershell
   pytest tests/
   ```

2. **Run API tests**:
   ```powershell
   python test_api.py
   ```

3. **Run database tests**:
   ```powershell
   python test_db.py
   ```

### Pre-Production Checklist

Before committing to GitHub and deploying to Heroku:

- [ ] All tests pass
- [ ] Environment variables are properly configured (no hardcoded secrets)
- [ ] `.env` is in `.gitignore` (it should be)
- [ ] Security setup is complete
- [ ] Application runs locally without errors
- [ ] Procfile and runtime.txt are present (for Heroku)
- [ ] OpenAI API key is set (if using OpenAI mode)

### Deployment to Heroku

1. **Commit your changes to Git**:
   ```powershell
   git add .
   git commit -m "Prepare for production deployment"
   git push origin main
   ```

2. **Create a Heroku app**:
   ```powershell
   heroku create your-app-name
   ```

3. **Set environment variables on Heroku**:
   ```powershell
   heroku config:set FLASK_ENV=production
   heroku config:set OPENAI_API_KEY=your-openai-api-key
   heroku config:set DATABASE_URL=your-postgresql-url
   # Set other variables as needed
   ```

4. **Deploy to Heroku**:
   ```powershell
   git push heroku main
   ```

5. **Open the deployed app** (database tables will be created automatically):
   ```powershell
   heroku open
   ```

### Configuration

#### Environment Variables
Create a `.env` file in the root directory:

```env
FLASK_ENV=development  # or production
FLASK_SECRET_KEY=your-secure-secret-key
LLM_MODE=mock  # or openai
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=sqlite:///instance/app.db  # or PostgreSQL URL for production
```

#### LLM Modes
- **mock**: Uses deterministic mock data (default, no API key needed)
- **openai**: Uses GPT-4o-mini for real risk analysis (requires API key)

#### Database
- **Development**: SQLite (automatic)
- **Production**: PostgreSQL (set DATABASE_URL)

## Usage

### User Management
- **Register**: Create a new account with email, first name, and last name
- **Login**: Authenticate with your email and password
- **Logout**: End your session

### Company Risk Requests
- **Add Companies**: Enter 1-5 company names to request risk analysis
- **List Companies**: View companies you've requested with risk counts
- **Show Risks**: Display detailed risk factors in a table format with numbered lists and alternating row colors for improved readability

### Administrator Access
- **Admin Tools**: Available only to kristina@erm-strategies.com - provides access to Flask-Admin interface for database management
- **Database Management**: View, edit, add, and delete users, companies, and risk data through the web interface

### Risk Categories
The application analyzes companies across five risk categories:
- Strategic
- Financial
- Legal
- Operational
- Technology

Each category contains up to 3 risk factors, displayed as numbered lists for clarity.

## Configuration

### LLM Mode
- **Mock Mode** (default): Uses deterministic mock data, no API key required
- **OpenAI Mode**: Uses GPT-4o-mini for real risk analysis

To enable OpenAI mode, set environment variables:
```powershell
$env:LLM_MODE = "openai"
$env:OPENAI_API_KEY = "your-api-key-here"
```

### Flask Secret Key
Set a secure secret key for sessions:
```powershell
$env:FLASK_SECRET_KEY = "your-secure-secret-key"
```

### Database Configuration
- **Development**: Uses SQLite database (`instance/project.db`)
- **Production**: Uses PostgreSQL via `DATABASE_URL` environment variable (automatically set on Heroku)

## Project Structure

```
├── web_app.py          # Main Flask application with database models
├── models.py           # SQLAlchemy database models
├── migrate.py          # Database migration script
├── main.py             # CLI prototype (legacy)
├── instance/           # Database files (created automatically)
│   └── project.db      # SQLite database (development)
├── requirements.txt    # Python dependencies
├── static/             # Static files (CSS, JS, images)
│   └── styles.css      # Application stylesheets
├── templates/          # HTML templates
│   ├── index.html      # Main application page
│   └── login.html      # Login/registration page
├── tests/              # Test files
└── README.md           # This file
```

## Data Storage

The application uses SQLAlchemy ORM with the following database models:

- **User**: User accounts with authentication (email, password hash, user ID)
- **Company**: Company information (name, creation timestamp)
- **UserCompany**: Many-to-many relationship between users and companies (with timestamps)
- **Risk**: Individual risk factors (company, category, description)

### Database Migration
Existing data from JSON files (`users.json`, `companies_data.json`) has been migrated to the SQL database. The migration script (`migrate.py`) handles this one-time process.

## Deployment

### Heroku Deployment
1. Create a Heroku app
2. Add PostgreSQL add-on: `heroku addons:create heroku-postgresql:hobby-dev`
3. Set environment variables:
   ```bash
   heroku config:set LLM_MODE=openai
   heroku config:set OPENAI_API_KEY=your-api-key
   heroku config:set FLASK_SECRET_KEY=your-secure-secret
   ```
4. Deploy the application

The application automatically detects the `DATABASE_URL` environment variable and uses PostgreSQL in production.

### AWS Migration
The SQLAlchemy setup makes migration to AWS RDS straightforward:
- Change `DATABASE_URL` to point to RDS PostgreSQL instance
- No code changes required due to ORM abstraction

## Dependencies

Key dependencies include:
- Flask: Web framework
- SQLAlchemy: Database ORM
- Flask-Admin: Administrative interface
- OpenAI: AI-powered risk analysis
- Werkzeug: Password hashing and utilities
- psycopg2-binary: PostgreSQL driver (production)

