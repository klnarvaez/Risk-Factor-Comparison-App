# API Documentation - Risk Factor Comparison App

This document describes the REST API endpoints available for programmatic access to the Risk Factor Comparison application.

## Authentication

All API endpoints (except `/api/v1/health`) require authentication using an API key. Include your API key in the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

### Getting an API Key

1. Log in to the web application
2. Go to your Profile page (`/profile`)
3. In the "API Access" section, click "Generate API Key"
4. Copy the generated key and store it securely

## Base URL

```
http://your-domain.com/api/v1
```

## Endpoints

### Health Check

**GET** `/api/v1/health`

Basic health check endpoint. No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "version": "v1",
  "message": "API is operational"
}
```

### Get Companies

**GET** `/api/v1/companies`

Returns a list of companies associated with the authenticated user.

**Response:**
```json
{
  "companies": [
    {
      "id": 1,
      "name": "Apple Inc.",
      "added_at": "2024-01-15T10:30:00"
    },
    {
      "id": 2,
      "name": "Microsoft Corporation",
      "added_at": "2024-01-16T14:20:00"
    }
  ],
  "count": 2
}
```

### Get Companies with Risks

**GET** `/api/v1/companies/risks`

Returns a list of companies and their associated risks for the authenticated user.

**Response:**
```json
{
  "companies": [
    {
      "id": 1,
      "name": "Apple Inc.",
      "risks": {
        "Strategic": ["Market competition risk", "Technology disruption"],
        "Financial": ["Currency fluctuation", "Supply chain costs"],
        "Legal": ["Regulatory compliance", "Intellectual property"],
        "Operational": ["Supply chain disruption", "Quality control"],
        "Technology": ["Cybersecurity threats", "Data privacy"]
      },
      "added_at": "2024-01-15T10:30:00"
    }
  ],
  "count": 1
}
```

### Add Companies

**POST** `/api/v1/companies`

Adds companies to the authenticated user's account. If a company does not already exist in the system, the API creates it automatically and fetches associated risk data from our connected LLM.

**Request Body:**
```json
{
  "companies": ["Apple Inc.", "Microsoft Corporation"]
}
```

**Constraints:**
- Maximum 5 companies per request
- All company names must be strings
- Company records do not need to exist before making this request

**Success Response (201):**
```json
{
  "message": "Companies processed successfully",
  "added_companies": [
    {
      "name": "Apple Inc.",
      "existing": true,
      "risk_count": 15
    },
    {
      "name": "NewCompany Inc.",
      "existing": false,
      "risk_count": 9
    }
  ],
  "skipped_companies": [],
  "details": [
    "Added access to 'Apple Inc.' with 15 risk items",
    "Stored 9 risk items for NewCompany Inc."
  ]
}
```

**Error Response (400):**
```json
{
  "error": "Invalid companies data",
  "message": "\"companies\" must be an array of strings"
}
```

### Delete Company

**DELETE** `/api/v1/companies/{company_name}`

Removes a company association from the authenticated user's account. This does not delete the company from the system, only the user's access to it.

**URL Parameters:**
- `company_name`: The exact name of the company to remove

**Success Response (200):**
```json
{
  "message": "Successfully removed company 'Apple Inc.' from your account",
  "company_name": "Apple Inc."
}
```

**Error Response (404):**
```json
{
  "error": "Company not found",
  "message": "Company 'NonExistent Corp' does not exist in the system"
}
```

## Error Responses

All endpoints return appropriate HTTP status codes and JSON error messages:

- **400 Bad Request**: Invalid request data or validation errors
- **401 Unauthorized**: Missing or invalid API key
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server-side errors

**Error Response Format:**
```json
{
  "error": "ErrorType",
  "message": "Human-readable error description"
}
```

## Rate Limiting

Currently, there are no rate limits implemented. Consider implementing rate limiting for production use.

## Data Formats

- **Request Content-Type**: `application/json`
- **Response Content-Type**: `application/json`
- **Date Format**: ISO 8601 (`YYYY-MM-DDTHH:MM:SS`)

## Security Notes

- API keys provide full access to your account data
- Store API keys securely (never in code or version control)
- Regenerate API keys periodically for security
- Use HTTPS in production
- Monitor API usage for suspicious activity

## Testing

Use the included test script to verify API functionality:

```bash
python test_api.py
```

The test script will check all endpoints and report results.

## Examples

### Python Example

```python
import requests

# Configuration
BASE_URL = "http://localhost:5000/api/v1"
API_KEY = "your_api_key_here"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Get companies
response = requests.get(f"{BASE_URL}/companies", headers=headers)
companies = response.json()

# Add companies
new_companies = {"companies": ["Tesla Inc.", "Amazon.com Inc."]}
response = requests.post(f"{BASE_URL}/companies", headers=headers, json=new_companies)

# Delete company
response = requests.delete(f"{BASE_URL}/companies/Tesla Inc.", headers=headers)
```

### cURL Examples

```bash
# Health check
curl http://localhost:5000/api/v1/health

# Get companies
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:5000/api/v1/companies

# Add companies
curl -X POST \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"companies": ["Apple Inc.", "Microsoft Corporation"]}' \
     http://localhost:5000/api/v1/companies

# Delete company
curl -X DELETE \
     -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:5000/api/v1/companies/Apple%20Inc.
```

## Changelog

### Version 1.0
- Initial API release
- Basic CRUD operations for companies
- API key authentication
- Health check endpoint