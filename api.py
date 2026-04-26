#!/usr/bin/env python3
"""
API Routes for Risk Factor Comparison App

This module contains REST API endpoints for programmatic access to the application.
All endpoints require authentication via API key in the Authorization header.
"""

import os
import json
import re
from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from models import db, User, Company, UserCompany, Risk
from typing import List, Dict, Any
from jsonschema import validate
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Categories for risk classification
CATEGORIES = ["Strategic", "Financial", "Legal", "Operational", "Technology"]

SCHEMA = {
    "type": "object",
    "properties": {cat: {"type": "array", "items": {"type": "string"}} for cat in CATEGORIES},
    "required": CATEGORIES,
    "additionalProperties": False,
}

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

# Initialize adapter
adapter = LLMAdapter()

def sanitize(name: str) -> str:
    """Sanitize string input by stripping whitespace."""
    return name.strip()

def api_auth_required(f):
    """
    Decorator to require API key authentication for routes.

    Expects Authorization header in format: "Bearer <api_key>"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({
                'error': 'Missing or invalid authorization header',
                'message': 'Include your API key in the Authorization header: "Authorization: Bearer YOUR_API_KEY"'
            }), 401

        api_key = auth_header.replace('Bearer ', '', 1).strip()

        if not api_key:
            return jsonify({
                'error': 'Missing API key',
                'message': 'API key is required'
            }), 401

        # Find user by API key
        user = User.query.filter_by(api_key=api_key).first()
        if not user:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is not valid'
            }), 401

        # Add user to request context
        request.api_user = user
        return f(*args, **kwargs)

    return decorated_function

@api_bp.route('/companies', methods=['GET'])
@api_auth_required
def get_companies():
    """
    Get list of companies for the authenticated user.

    Returns:
        JSON array of company objects with basic information
    """
    user = request.api_user

    companies = []
    for uc in user.companies:
        company = uc.company
        companies.append({
            'id': company.id,
            'name': company.name,
            'added_at': uc.added_at.isoformat() if uc.added_at else None
        })

    return jsonify({
        'companies': companies,
        'count': len(companies)
    }), 200

@api_bp.route('/companies/risks', methods=['GET'])
@api_auth_required
def get_companies_with_risks():
    """
    Get list of companies and their associated risks for the authenticated user.

    Returns:
        JSON array of company objects with risk data
    """
    user = request.api_user

    companies = []
    for uc in user.companies:
        company = uc.company
        risks = {}

        # Get risks for each category
        for category in CATEGORIES:
            risk_objs = Risk.query.filter_by(company=company, category=category).all()
            risks[category] = [r.description for r in risk_objs]

        companies.append({
            'id': company.id,
            'name': company.name,
            'risks': risks,
            'added_at': uc.added_at.isoformat() if uc.added_at else None
        })

    return jsonify({
        'companies': companies,
        'count': len(companies)
    }), 200

@api_bp.route('/companies/<company_name>', methods=['DELETE'])
@api_auth_required
def delete_company(company_name: str):
    """
    Remove a company association for the authenticated user.

    Args:
        company_name: Name of the company to remove

    Returns:
        Success message or error if company not found
    """
    user = request.api_user
    company_name = sanitize(company_name)

    if not company_name:
        return jsonify({
            'error': 'Invalid company name',
            'message': 'Company name cannot be empty'
        }), 400

    # Find the company
    company = Company.query.filter_by(name=company_name).first()
    if not company:
        return jsonify({
            'error': 'Company not found',
            'message': f'Company "{company_name}" does not exist in the system'
        }), 404

    # Check if user has access to this company
    uc = UserCompany.query.filter_by(user_id=user.id, company_id=company.id).first()
    if not uc:
        return jsonify({
            'error': 'Company not associated',
            'message': f'You do not have access to company "{company_name}"'
        }), 404

    # Remove the association
    try:
        db.session.delete(uc)
        db.session.commit()

        return jsonify({
            'message': f'Successfully removed company "{company_name}" from your account',
            'company_name': company_name
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete company association: {e}")
        return jsonify({
            'error': 'Database error',
            'message': 'Failed to remove company association'
        }), 500

@api_bp.route('/companies', methods=['POST'])
@api_auth_required
def add_companies():
    """
    Add companies for the authenticated user.

    Expects JSON body with 'companies' array containing company names.
    Maximum 5 companies allowed per request.

    Returns:
        Success message with details of added companies
    """
    user = request.api_user

    # Validate JSON request
    if not request.is_json:
        return jsonify({
            'error': 'Invalid content type',
            'message': 'Request must be JSON'
        }), 400

    data = request.get_json()
    if not data or 'companies' not in data:
        return jsonify({
            'error': 'Missing companies data',
            'message': 'Request body must contain a "companies" array'
        }), 400

    company_names = data['companies']
    if not isinstance(company_names, list):
        return jsonify({
            'error': 'Invalid companies data',
            'message': '"companies" must be an array of strings'
        }), 400

    # Validate company names
    if not (1 <= len(company_names) <= 5):
        return jsonify({
            'error': 'Invalid number of companies',
            'message': 'Must provide between 1 and 5 company names'
        }), 400

    # Sanitize and validate each company name
    sanitized_names = []
    for name in company_names:
        if not isinstance(name, str):
            return jsonify({
                'error': 'Invalid company name',
                'message': 'All company names must be strings'
            }), 400

        sanitized = sanitize(name)
        if not sanitized:
            continue  # Skip empty names

        if len(sanitized) > 100:  # Match database constraint
            return jsonify({
                'error': 'Company name too long',
                'message': f'Company name "{name}" exceeds maximum length of 100 characters'
            }), 400

        sanitized_names.append(sanitized)

    if not sanitized_names:
        return jsonify({
            'error': 'No valid company names',
            'message': 'All provided company names were empty or invalid'
        }), 400

    # Process companies (reuse existing logic from web_app.py)
    messages = []
    added_companies = []
    skipped_companies = []

    for name in sanitized_names:
        # Check if company already exists
        company = Company.query.filter_by(name=name).first()
        if company:
            # Check if user already has access
            existing = UserCompany.query.filter_by(user=user, company=company).first()
            if existing:
                messages.append(f"Company '{name}' already associated with your account")
                skipped_companies.append(name)
                continue
            # Add user to existing company
            user_company = UserCompany(user=user, company=company)
            db.session.add(user_company)
            total_risks = Risk.query.filter_by(company=company).count()
            messages.append(f"Added access to '{name}' with {total_risks} risk items")
            added_companies.append({
                'name': name,
                'existing': True,
                'risk_count': total_risks
            })
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
            added_companies.append({
                'name': name,
                'existing': False,
                'risk_count': total
            })

    try:
        db.session.commit()

        return jsonify({
            'message': 'Companies processed successfully',
            'added_companies': added_companies,
            'skipped_companies': skipped_companies,
            'details': messages
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to add companies: {e}")
        return jsonify({
            'error': 'Database error',
            'message': 'Failed to add companies to your account'
        }), 500

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint - no authentication required.

    Returns:
        Basic health status
    """
    return jsonify({
        'status': 'healthy',
        'version': 'v1',
        'message': 'API is operational'
    }), 200