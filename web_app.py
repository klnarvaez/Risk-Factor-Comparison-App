#!/usr/bin/env python3
"""Web prototype for Risk Factor Comparison App using Flask and SQL Database
"""

import os
import json
import re
import hashlib
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from flask import Flask, request, render_template_string, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from jsonschema import validate
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
import uuid
from datetime import datetime
from functools import wraps

from models import db, User, Company, UserCompany, Risk
from api import api_bp

CATEGORIES = ["Strategic", "Financial", "Legal", "Operational", "Technology"]

SCHEMA = {
    "type": "object",
    "properties": {cat: {"type": "array", "items": {"type": "string"}} for cat in CATEGORIES},
    "required": CATEGORIES,
    "additionalProperties": False,
}

def sanitize(name: str) -> str:
    """Sanitize string input by stripping whitespace."""
    return name.strip()

def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength. 
    
    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*)
    
    Returns (is_valid, error_message)
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit."
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
        return False, "Password must contain at least one special character (!@#$%^&*)."
    
    return True, ""

def sanitize_input(value: str, max_length: int = 255, field_name: str = "input") -> Tuple[bool, str]:
    """Sanitize and validate user input.
    
    Returns (is_valid, sanitized_value_or_error_message)
    """
    if not value:
        return False, f"{field_name} cannot be empty."
    
    value = value.strip()
    
    if len(value) > max_length:
        return False, f"{field_name} cannot exceed {max_length} characters."
    
    # Basic XSS prevention - remove script tags and dangerous characters
    value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r'on\w+\s*=', '', value, flags=re.IGNORECASE)  # Remove event handlers
    
    return True, value

def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format.
    
    Returns (is_valid, error_message)
    """
    email = email.lower().strip()
    
    if not email:
        return False, "Email cannot be empty."
    
    if len(email) > 120:
        return False, "Email cannot exceed 120 characters."
    
    # Basic email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Please enter a valid email address."
    
    return True, ""

def extract_json_from_text(text: str) -> dict:
    """Attempt to extract a JSON object from arbitrary text.

    Tries direct json.loads first, then searches for the first balanced {...} block.
    Raises ValueError if no JSON object can be parsed.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # find first '{' and match balanced braces
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object found in text")
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    fragment = text[start : i + 1]
                    try:
                        return json.loads(fragment)
                    except Exception:
                        break
        # fallback: try regex to find a JSON-like substring
        matches = re.findall(r"(\{.*\})", text, flags=re.DOTALL)
        for m in matches:
            try:
                return json.loads(m)
            except Exception:
                continue
        raise ValueError("Could not extract valid JSON from text")

def validate_and_normalize(data: dict, top_n: int = 3) -> Dict[str, List[str]]:
    """Validate that `data` matches the risk categories schema and normalize lists.

    Returns a dict mapping each category to a list of up to `top_n` cleaned strings.
    Raises ValidationError on failure.
    """
    try:
        validate(instance=data, schema=SCHEMA)
    except JSONSchemaValidationError as e:
        raise ValidationError(f"Schema validation error: {e.message}")

    out: Dict[str, List[str]] = {}
    for cat in CATEGORIES:
        items = data.get(cat, [])
        normalized = []
        for it in items:
            if isinstance(it, str):
                s = it.strip()
                if s:
                    normalized.append(s)
            else:
                # ignore non-string items
                continue
            if len(normalized) >= top_n:
                break
        out[cat] = normalized
    return out

class ValidationError(Exception):
    pass

class LLMAdapter:
    """Simple LLM adapter with a deterministic mock mode and optional OpenAI integration.

    Mode selection via env var `LLM_MODE` (values: "mock" or "openai").
    OpenAI usage requires `OPENAI_API_KEY` in the environment.
    """

    def __init__(self, mode: str = None):
        self.mode = (mode or os.getenv("LLM_MODE", "mock")).lower()
        self.openai = None
        # in-memory cache: key=(company_name_lower, top_n) -> normalized result dict
        self._cache = {}
        # simple counter to help tests and observability in prototype
        self._api_calls = 0

        if self.mode == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                print("OPENAI_API_KEY not found in env; falling back to mock mode.")
                self.mode = "mock"
            else:
                try:
                    # Prefer the new OpenAI client (openai>=1.0.0)
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=key)
                        self.openai = client
                        self._openai_new_client = True
                    except Exception:
                        # Fall back to older openai module interface
                        import openai as openai_module
                        openai_module.api_key = key
                        self.openai = openai_module
                        self._openai_new_client = False
                except Exception as e:
                    print("Failed to import openai library; falling back to mock mode.", e)
                    self.mode = "mock"

    def get_company_risks(self, company_name: str, top_n: int = 3) -> Dict[str, List[str]]:
        """Return cached results when available; otherwise fetch and cache them."""
        key = (company_name.strip().lower(), int(top_n))
        if key in self._cache:
            return self._cache[key]

        # not cached — call the model/provider
        self._api_calls += 1
        if self.mode == "mock":
            result = self._mock_risks(company_name, top_n)
        elif self.mode == "openai":
            result = self._openai_risks(company_name, top_n)
        else:
            result = self._mock_risks(company_name, top_n)

        # store in cache
        self._cache[key] = result
        return result

    @property
    def api_call_count(self) -> int:
        return self._api_calls

    def clear_cache(self):
        self._cache.clear()

    def cache_keys(self):
        return list(self._cache.keys())

    def _mock_risks(self, company_name: str, top_n: int) -> Dict[str, List[str]]:
        # Deterministic, readable mock output for local testing.
        out = {}
        seed = company_name.lower().split()[0]
        for i, cat in enumerate(CATEGORIES):
            out[cat] = [f"{cat} risk {j+1} for {company_name}" for j in range(top_n)]
        return out

    def _openai_risks(self, company_name: str, top_n: int) -> Dict[str, List[str]]:
        prompt = (
            f"Extract the top {top_n} risk excerpts for the company named \"{company_name}\" "
            "and return a JSON object with the following keys: Strategic, Financial, Legal, Operational, Technology."
            "Each key must map to a list of strings (risk excerpts). Return only valid JSON."
        )
        try:
            if getattr(self, "_openai_new_client", False):
                # openai.OpenAI client (>=1.0.0)
                resp = self.openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                # Support both attribute access and dict-like access
                try:
                    content = resp.choices[0].message.content
                except Exception:
                    content = resp["choices"][0]["message"]["content"]
            else:
                # Legacy openai package interface
                resp = self.openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                content = resp["choices"][0]["message"]["content"]
            # Try to parse and validate JSON robustly
            try:
                raw = None
                try:
                    raw = extract_json_from_text(content)
                except Exception as e:
                    print("Failed to extract JSON from model output; falling back to mock. Error:", e)
                    return self._mock_risks(company_name, top_n)

                try:
                    normalized = validate_and_normalize(raw, top_n=top_n)
                    return normalized
                except Exception as e:
                    print("Validation of model JSON failed; falling back to mock. Error:", e)
                    return self._mock_risks(company_name, top_n)
            except Exception as e:
                print("LLM validation integration failed; falling back to mock. Error:", e)
                return self._mock_risks(company_name, top_n)
        except Exception as e:
            print("OpenAI query failed, falling back to mock. Error:", e)
            return self._mock_risks(company_name, top_n)

def authenticate_user(email: str, password: str) -> Tuple[bool, Optional[Dict[str, str]]]:
    """Authenticate a user. Returns (success, user_data)."""
    user = User.query.filter_by(email=email.lower()).first()
    if user and check_password_hash(user.password_hash, password):
        return True, {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "user_id": user.user_id
        }
    return False, None

def register_user(email: str, first_name: str, last_name: str, password: str) -> Tuple[bool, str]:
    """Register a new user. Returns (success, message)."""
    # Validate and sanitize inputs
    is_valid, error = validate_email(email)
    if not is_valid:
        return False, error
    
    email = email.lower()
    
    # Check if email already registered
    if User.query.filter_by(email=email).first():
        return False, "Email already registered."
    
    # Validate first name
    is_valid, first_name = sanitize_input(first_name, max_length=50, field_name="First name")
    if not is_valid:
        return False, first_name
    
    # Validate last name
    is_valid, last_name = sanitize_input(last_name, max_length=50, field_name="Last name")
    if not is_valid:
        return False, last_name
    
    # Validate password strength
    is_valid, error = validate_password(password)
    if not is_valid:
        return False, error
    
    password_hash = generate_password_hash(password)
    user_id = str(uuid.uuid4())

    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=password_hash,
        user_id=user_id
    )

    try:
        db.session.add(user)
        db.session.commit()
        return True, "Registration successful!"
    except Exception as e:
        db.session.rollback()
        return False, f"Failed to save user data: {e}"

def add_companies(names: List[str], user_id: str) -> str:
    """Add companies and return status message."""
    if not (1 <= len(names) <= 5):
        return "Please enter between 1 and 5 company names."
    messages = []
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return "User not found."

    for name in names:
        name = sanitize(name)
        if not name:
            continue

        # Check if company already exists
        company = Company.query.filter_by(name=name).first()
        if company:
            # Check if user already has access
            existing = UserCompany.query.filter_by(user=user, company=company).first()
            if existing:
                messages.append(f"Company '{name}' already requested by you. Skipping.")
                continue
            # Add user to existing company
            user_company = UserCompany(user=user, company=company)
            db.session.add(user_company)
            total_risks = Risk.query.filter_by(company=company).count()
            messages.append(f"Added access to '{name}' with {total_risks} risk items.")
        else:
            # Company not found, fetch new risks from LLM
            messages.append(f"Fetching risks for: {name} ...")
            risks = adapter.get_company_risks(name, top_n=3)
            company = Company(name=name)
            db.session.add(company)

            # Add risks
            for category in CATEGORIES:
                for risk_desc in risks.get(category, []):
                    risk = Risk(company=company, category=category, description=risk_desc)
                    db.session.add(risk)

            # Add user association
            user_company = UserCompany(user=user, company=company)
            db.session.add(user_company)

            total = sum(len(risks.get(c, [])) for c in CATEGORIES)
            messages.append(f"Stored {total} risk items for {name}.")

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            messages.append(f"Warning: Failed to save data after adding {name}: {e}")

    return "<br>".join(messages)

def list_companies(user_id: str) -> List[Dict[str, any]]:
    """Return list of companies for the user."""
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return []

    companies = []
    for uc in user.companies:
        company = uc.company
        counts = {}
        for category in CATEGORIES:
            counts[category] = Risk.query.filter_by(company=company, category=category).count()
        companies.append({'name': company.name, 'counts': counts})
    return companies

def show_risks(user_id: str) -> List[Dict[str, any]]:
    """Return list of companies with their risks."""
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return []

    companies = []
    for uc in user.companies:
        company = uc.company
        risks = {}
        for category in CATEGORIES:
            risk_objs = Risk.query.filter_by(company=company, category=category).all()
            risks[category] = [r.description for r in risk_objs]
        companies.append({'name': company.name, 'risks': risks})
    return companies

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///project.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Register API blueprint
app.register_blueprint(api_bp)

# Initialize adapter
adapter = LLMAdapter()

# Admin access control
ADMIN_EMAIL = 'kristina@erm-strategies.com'

# Session timeout in seconds (30 minutes)
SESSION_TIMEOUT = 30 * 60

def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if session['user']['email'] != ADMIN_EMAIL:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def merge_users(primary_user_id: str, secondary_user_id: str, action: str) -> Tuple[bool, str]:
    """Merge two user accounts.
    
    Args:
        primary_user_id: User ID to merge INTO (primary user will be kept)
        secondary_user_id: User ID to merge FROM (secondary user will be deleted/archived)
        action: 'consolidate' to delete secondary user, 'archive' to mark as inactive
    
    Returns:
        (success: bool, message: str)
    """
    if primary_user_id == secondary_user_id:
        return False, "Cannot merge a user with themselves."
    
    primary_user = User.query.filter_by(user_id=primary_user_id).first()
    secondary_user = User.query.filter_by(user_id=secondary_user_id).first()
    
    if not primary_user or not secondary_user:
        return False, "One or both users not found."
    
    try:
        # Move all UserCompany associations from secondary to primary
        secondary_assocs = UserCompany.query.filter_by(user_id=secondary_user.id).all()
        
        for assoc in secondary_assocs:
            # Check if primary user already has this company
            existing = UserCompany.query.filter_by(
                user_id=primary_user.id,
                company_id=assoc.company_id
            ).first()
            
            if not existing:
                # Move the association
                assoc.user_id = primary_user.id
            else:
                # Duplicate would be created, just remove the secondary one
                db.session.delete(assoc)
        
        if action == 'consolidate':
            # Delete the secondary user
            db.session.delete(secondary_user)
            message = f"Merged {secondary_user.email} into {primary_user.email} (deleted secondary user)"
        elif action == 'archive':
            # Mark as archived by adding a note to first_name (simple approach)
            secondary_user.first_name = f"[ARCHIVED] {secondary_user.first_name}"
            message = f"Merged {secondary_user.email} into {primary_user.email} (archived secondary user)"
        else:
            return False, "Invalid action. Use 'consolidate' or 'archive'."
        
        db.session.commit()
        return True, message
    except Exception as e:
        db.session.rollback()
        return False, f"Merge failed: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    # Check if user is logged in
    if 'user' not in session:
        return redirect(url_for('login'))
    
    message = ""
    companies_list = None
    risks_data = None
    show_admin_button = session['user']['email'] == 'kristina@erm-strategies.com'
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'logout':
            session.clear()
            return redirect(url_for('login'))
        elif action == 'add':
            companies_input = request.form.get('companies', '')
            names = [sanitize(n) for n in companies_input.split(',') if sanitize(n)]
            message = add_companies(names, session['user']['user_id'])
        elif action == 'list':
            companies_list = list_companies(session['user']['user_id'])
        elif action == 'show':
            risks_data = show_risks(session['user']['user_id'])
    
    return render_template('index.html', first_name=session['user']['first_name'], message=message, companies_list=companies_list, risks_data=risks_data, categories=CATEGORIES, show_admin_button=show_admin_button)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        success, user_data = authenticate_user(email, password)
        if success:
            session['user'] = user_data
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password.')
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    firstname = request.form.get('firstname', '').strip()
    lastname = request.form.get('lastname', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    
    success, message = register_user(email, firstname, lastname, password)
    
    if success:
        # Auto-login after registration
        user = User.query.filter_by(email=email).first()
        user_data = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_id': user.user_id
        }
        session['user'] = user_data
        return redirect(url_for('index'))
    else:
        return render_template('login.html', error=message)

# =================================
# USER PROFILE ROUTES
# =================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page - view and edit user information."""
    user = User.query.filter_by(user_id=session['user']['user_id']).first()
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    message = ""
    message_type = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'logout':
            session.clear()
            return redirect(url_for('login'))
        
        elif action == 'update_info':
            # Update personal information
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            
            # Validate inputs
            is_valid, error = sanitize_input(first_name, max_length=50, field_name="First name")
            if not is_valid:
                message = error
                message_type = "error"
            else:
                is_valid, error = sanitize_input(last_name, max_length=50, field_name="Last name")
                if not is_valid:
                    message = error
                    message_type = "error"
                else:
                    is_valid, error = validate_email(email)
                    if not is_valid:
                        message = error
                        message_type = "error"
                    else:
                        # Check if email is already used by another user
                        existing_user = User.query.filter_by(email=email).first()
                        if existing_user and existing_user.id != user.id:
                            message = "This email is already registered with another account."
                            message_type = "error"
                        else:
                            try:
                                user.first_name = first_name
                                user.last_name = last_name
                                user.email = email
                                db.session.commit()
                                
                                # Update session
                                session['user']['first_name'] = first_name
                                session['user']['last_name'] = last_name
                                session['user']['email'] = email
                                session.modified = True
                                
                                message = "Personal information updated successfully!"
                                message_type = "success"
                            except Exception as e:
                                db.session.rollback()
                                message = f"Failed to update information: {str(e)}"
                                message_type = "error"
        
        elif action == 'change_password':
            # Change password
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Verify current password
            if not check_password_hash(user.password_hash, current_password):
                message = "Current password is incorrect."
                message_type = "error"
            elif new_password != confirm_password:
                message = "New passwords do not match."
                message_type = "error"
            else:
                # Validate new password
                is_valid, error = validate_password(new_password)
                if not is_valid:
                    message = error
                    message_type = "error"
                else:
                    # Don't allow reusing the same password
                    if check_password_hash(user.password_hash, new_password):
                        message = "New password cannot be the same as your current password."
                        message_type = "error"
                    else:
                        try:
                            user.password_hash = generate_password_hash(new_password)
                            db.session.commit()
                            message = "Password changed successfully!"
                            message_type = "success"
                        except Exception as e:
                            db.session.rollback()
                            message = f"Failed to change password: {str(e)}"
                            message_type = "error"
        
        elif action == 'delete_company':
            # Delete company association
            company_id = request.form.get('company_id')
            try:
                company_id = int(company_id)
                # Find and delete the UserCompany association
                uc = UserCompany.query.filter_by(user_id=user.id, company_id=company_id).first()
                if uc:
                    db.session.delete(uc)
                    db.session.commit()
                    message = "Company removed from your account successfully!"
                    message_type = "success"
                else:
                    message = "Company not found in your account."
                    message_type = "warning"
            except Exception as e:
                db.session.rollback()
                message = f"Failed to remove company: {str(e)}"
                message_type = "error"
        
        elif action == 'generate_api_key':
            # Generate new API key
            if user.api_key:
                message = "You already have an API key. Delete it first if you want to generate a new one."
                message_type = "warning"
            else:
                try:
                    # Generate a secure API key
                    import secrets
                    user.api_key = secrets.token_hex(32)  # 64 character hex string
                    db.session.commit()
                    message = "API key generated successfully!"
                    message_type = "success"
                except Exception as e:
                    db.session.rollback()
                    message = f"Failed to generate API key: {str(e)}"
                    message_type = "error"
        
        elif action == 'delete_api_key':
            # Delete API key
            if not user.api_key:
                message = "You don't have an API key to delete."
                message_type = "warning"
            else:
                try:
                    user.api_key = None
                    db.session.commit()
                    message = "API key deleted successfully!"
                    message_type = "success"
                except Exception as e:
                    db.session.rollback()
                    message = f"Failed to delete API key: {str(e)}"
                    message_type = "error"
    
    # Get user's companies
    companies = []
    for uc in user.companies:
        companies.append({
            'company_id': uc.company.id,
            'name': uc.company.name
        })
    
    return render_template('profile.html', user=user, companies=companies, message=message, message_type=message_type)

@app.route('/manage/companies', methods=['GET', 'POST'])
@login_required
def manage_companies():
    """Dedicated page for managing companies associated with the current user."""
    user = User.query.filter_by(user_id=session['user']['user_id']).first()
    if not user:
        session.clear()
        return redirect(url_for('login'))

    message = ""
    message_type = ""

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delete_company':
            company_id = request.form.get('company_id')
            try:
                company_id = int(company_id)
                uc = UserCompany.query.filter_by(user_id=user.id, company_id=company_id).first()
                if uc:
                    db.session.delete(uc)
                    db.session.commit()
                    message = "Company removed from your account successfully!"
                    message_type = "success"
                else:
                    message = "Company not found in your account."
                    message_type = "warning"
            except Exception as e:
                db.session.rollback()
                message = f"Failed to remove company: {str(e)}"
                message_type = "error"

    companies = []
    for uc in user.companies:
        companies.append({
            'company_id': uc.company.id,
            'name': uc.company.name
        })

    return render_template('manage_companies.html', user=user, companies=companies, message=message, message_type=message_type)

# =================================
# ADMIN ROUTES
# =================================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard home page."""
    return render_template('admin/dashboard.html')

@app.route('/admin/users')
@admin_required
def admin_users():
    """List all users."""
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/companies')
@admin_required
def admin_companies():
    """List all companies."""
    companies = Company.query.all()
    return render_template('admin/companies.html', companies=companies)

@app.route('/admin/risks')
@admin_required
def admin_risks():
    """List all risks."""
    risks = Risk.query.all()
    companies_map = {c.id: c.name for c in Company.query.all()}
    return render_template('admin/risks.html', risks=risks, companies_map=companies_map)

@app.route('/admin/associations')
@admin_required
def admin_associations():
    """List all user-company associations."""
    associations = UserCompany.query.all()
    users_map = {u.id: f"{u.first_name} {u.last_name} ({u.email})" for u in User.query.all()}
    companies_map = {c.id: c.name for c in Company.query.all()}
    return render_template('admin/associations.html', associations=associations, users_map=users_map, companies_map=companies_map)

@app.route('/admin/users/<user_key>', methods=['GET', 'POST'])
@admin_required
def admin_user_detail(user_key):
    """View/edit user details supporting numeric ID or user_id UUID-like key."""
    # Accept /admin/users/<id> or /admin/users/<user_id>
    user = None
    if user_key.isdigit():
        user = User.query.get(int(user_key))
    if not user:
        user = User.query.filter_by(user_id=user_key).first()

    if not user:
        return "User not found", 404

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update':
            user.first_name = request.form.get('first_name', '').strip()
            user.last_name = request.form.get('last_name', '').strip()
            try:
                db.session.commit()
                message = "User updated successfully."
            except Exception as e:
                db.session.rollback()
                message = f"Failed to update user: {str(e)}"
            return render_template('admin/user_detail.html', user=user, message=message)
        
        elif action == 'delete':
            try:
                # Delete all associations first
                UserCompany.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()
                return redirect(url_for('admin_users'))
            except Exception as e:
                db.session.rollback()
                message = f"Failed to delete user: {str(e)}"
                return render_template('admin/user_detail.html', user=user, message=message)
    
    return render_template('admin/user_detail.html', user=user)

@app.route('/admin/companies/<int:company_id>', methods=['GET', 'POST'])
@admin_required
def admin_company_detail(company_id):
    """View/edit company details."""
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update':
            company.name = request.form.get('name', '').strip()
            try:
                db.session.commit()
                message = "Company updated successfully."
            except Exception as e:
                db.session.rollback()
                message = f"Failed to update company: {str(e)}"
            return render_template('admin/company_detail.html', company=company, message=message)
        
        elif action == 'delete':
            try:
                # Delete associated risks and associations
                Risk.query.filter_by(company_id=company.id).delete()
                UserCompany.query.filter_by(company_id=company.id).delete()
                db.session.delete(company)
                db.session.commit()
                return redirect(url_for('admin_companies'))
            except Exception as e:
                db.session.rollback()
                message = f"Failed to delete company: {str(e)}"
                return render_template('admin/company_detail.html', company=company, message=message)
    
    return render_template('admin/company_detail.html', company=company)

@app.route('/admin/companies/add', methods=['POST'])
@admin_required
def admin_add_company():
    """Add a new company."""
    name = request.form.get('name', '').strip()
    
    if not name:
        return redirect(url_for('admin_companies'))
    
    if Company.query.filter_by(name=name).first():
        # Company already exists, redirect
        return redirect(url_for('admin_companies'))
    
    try:
        company = Company(name=name)
        db.session.add(company)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    
    return redirect(url_for('admin_companies'))

@app.route('/admin/merge-users', methods=['POST'])
@admin_required
def admin_merge_users():
    """Merge two user accounts."""
    primary_user_id = request.form.get('primary_user_id', '').strip()
    secondary_user_id = request.form.get('secondary_user_id', '').strip()
    action = request.form.get('action', 'consolidate').strip()
    
    success, message = merge_users(primary_user_id, secondary_user_id, action)
    
    # Return JSON response or redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'success': success, 'message': message}
    
    users = User.query.all()
    return render_template('admin/users.html', users=users, merge_message=message)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)