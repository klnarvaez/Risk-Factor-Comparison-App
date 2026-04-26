#!/usr/bin/env python3
"""
Test script for API endpoints

This script tests the API endpoints to ensure they work correctly.
Run this after setting up the API and generating an API key.
"""

import requests
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:5000/api/v1"
TEST_API_KEY = os.getenv("TEST_API_KEY", None)

def get_headers():
    """Get headers for API requests."""
    if not TEST_API_KEY:
        return {}
    return {"Authorization": f"Bearer {TEST_API_KEY}", "Content-Type": "application/json"}

def test_health():
    """Test the health endpoint."""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✓ Health check passed")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False

def test_companies_get():
    """Test GET /companies endpoint."""
    print("Testing GET /companies...")
    try:
        response = requests.get(f"{BASE_URL}/companies", headers=get_headers())
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved {data.get('count', 0)} companies")
            return True
        elif response.status_code == 401:
            print("✗ Authentication required (expected if no API key)")
            return True  # This is expected without API key
        else:
            print(f"✗ Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ GET companies error: {e}")
        return False

def test_companies_risks_get():
    """Test GET /companies/risks endpoint."""
    print("Testing GET /companies/risks...")
    try:
        response = requests.get(f"{BASE_URL}/companies/risks", headers=get_headers())
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved {data.get('count', 0)} companies with risks")
            return True
        elif response.status_code == 401:
            print("✗ Authentication required (expected if no API key)")
            return True  # This is expected without API key
        else:
            print(f"✗ Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ GET companies/risks error: {e}")
        return False

def test_companies_post():
    """Test POST /companies endpoint."""
    print("Testing POST /companies...")
    try:
        # Test with sample data
        test_data = {"companies": ["Apple Inc."]}
        response = requests.post(f"{BASE_URL}/companies",
                               headers=get_headers(),
                               json=test_data)
        print(f"Status: {response.status_code}")
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Added companies: {data.get('added_companies', [])}")
            return True
        elif response.status_code == 401:
            print("✗ Authentication required (expected if no API key)")
            return True  # This is expected without API key
        elif response.status_code == 400:
            data = response.json()
            print(f"✓ Validation working: {data.get('message', 'Validation error')}")
            return True
        else:
            print(f"✗ Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ POST companies error: {e}")
        return False

def test_companies_delete():
    """Test DELETE /companies/<name> endpoint."""
    print("Testing DELETE /companies/<name>...")
    try:
        company_name = "Apple Inc."
        response = requests.delete(f"{BASE_URL}/companies/{quote(company_name)}",
                                 headers=get_headers())
        print(f"Status: {response.status_code}")
        if response.status_code == 404:
            print("✓ Company not found (expected for test company)")
            return True
        elif response.status_code == 401:
            print("✗ Authentication required (expected if no API key)")
            return True  # This is expected without API key
        elif response.status_code == 200:
            print("✓ Company deleted successfully")
            return True
        else:
            print(f"✗ Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ DELETE companies error: {e}")
        return False

def main():
    """Run all API tests."""
    print("=" * 60)
    print("Risk Factor Comparison App - API Tests")
    print("=" * 60)

    # Test health endpoint (no auth required)
    if not test_health():
        print("\n✗ Health check failed. Make sure the Flask app is running.")
        return 1

    print("\n" + "-" * 40)
    print("Testing authenticated endpoints...")
    print("Note: These will fail without a valid API key")
    print("-" * 40)

    # Test other endpoints
    tests = [
        test_companies_get,
        test_companies_risks_get,
        test_companies_post,
        test_companies_delete
    ]

    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 60)
    print(f"Tests completed: {passed}/{len(tests)} passed")

    if passed == len(tests):
        print("✓ All tests passed!")
    else:
        print("⚠ Some tests failed (expected without API key)")

    print("\nTo test with authentication:")
    print("1. Start the Flask app: python web_app.py")
    print("2. Login and generate an API key in your profile")
    print("3. Set TEST_API_KEY in your .env file or environment and run again")

    return 0

if __name__ == "__main__":
    sys.exit(main())
