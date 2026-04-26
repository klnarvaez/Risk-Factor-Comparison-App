# Risk Factor Comparison App - Security Documentation

## Overview
This document outlines all security measures implemented in the Risk Factor Comparison App to protect user data, ensure secure authentication, and maintain application integrity.

---

## 1. Authentication & Session Management

### 1.1 Password Security
- **Algorithm**: Passwords are hashed using `werkzeug.security.generate_password_hash()` which uses PBKDF2 with SHA256, including automatic salt generation.
- **Verification**: Passwords are verified using `werkzeug.security.check_password_hash()` for secure comparison.
- **Storage**: Only password hashes are stored in the database, never plain text passwords.
- **Requirements**:
  - Minimum 8 characters
  - At least one uppercase letter (A-Z)
  - At least one lowercase letter (a-z)
  - At least one digit (0-9)
  - At least one special character (!@#$%^&*)

### 1.2 Password Validation Function
The application implements strict password validation during registration and password changes:
```python
def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validates password strength against security requirements.
    Returns (is_valid, error_message)
    """
```

### 1.3 Session Management
- **Session Storage**: Flask sessions use secure cookies with the secret key
- **Session Timeout**: Configured for 30 minutes of inactivity
- **Session Clear**: Sessions are cleared on logout and when user is not authenticated
- **Secure Cookies**: Flask is configured with `app.secret_key` for session encryption

### 1.4 Authentication Flow
1. User credentials are validated in `authenticate_user()` function
2. Successful authentication creates a session with user data stored
3. All protected routes check for `'user' not in session` to enforce authentication
4. Sensitive operations require reauthentication (e.g., password changes)

---

## 2. Authorization & Access Control

### 2.1 Authentication Decorator
```python
def login_required(f):
    """Ensures only authenticated users can access a route."""
```
- Applied to `/profile` and other user-specific routes
- Redirects unauthenticated users to `/login`

### 2.2 Admin Authorization Decorator
```python
def admin_required(f):
    """Ensures only admin users can access admin routes."""
```
- Checks if user email matches `ADMIN_EMAIL`
- Redirects non-admin users to `/index`
- Applied to all `/admin/*` routes

### 2.3 Role-Based Access Control
- **Admin Email**: `kristina@erm-strategies.com` (configurable)
- Only admin can:
  - View all users
  - View all companies and risks
  - Delete companies
  - Manage user associations
  - Perform user merges

### 2.4 User-Level Access Control
- Users can only modify their own data
- Users can only view/manage their own companies
- Profile page checks if user matches current session user
- Company deletion removes only the user-company association, not the company itself

---

## 3. Input Validation & Sanitization

### 3.1 Email Validation
```python
def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validates email format and length.
    - Maximum length: 120 characters
    - Pattern: standard email regex validation
    - Returns (is_valid, error_message)
    """
```

### 3.2 General Input Sanitization
```python
def sanitize_input(value: str, max_length: int = 255, field_name: str = "input") -> Tuple[bool, str]:
    """
    Sanitizes and validates user input.
    - Removes leading/trailing whitespace
    - Enforces maximum length
    - Removes script tags to prevent XSS attacks
    - Removes event handlers (onclick, onerror, etc.)
    - Returns (is_valid, sanitized_value_or_error)
    """
```

### 3.3 Input Validation Applied To:
- First Name: Max 50 characters, sanitized
- Last Name: Max 50 characters, sanitized
- Email: Validated format, max 120 characters
- Company Names: Sanitized and limited
- All form inputs: Required and validated

### 3.4 XSS Prevention
- Script tags are stripped from user input
- Event handlers are removed
- HTML special characters are handled safely
- Jinja2 templates use auto-escaping by default

---

## 4. Database Security

### 4.1 SQL Injection Prevention
- **ORM Protection**: SQLAlchemy ORM prevents SQL injection through parameterized queries
- **No Raw SQL**: All database operations use ORM methods
- **Query Methods Used**:
  - `User.query.filter_by()` for exact matches
  - `User.query.get()` for ID lookups
  - `db.session.add/delete/commit` for modifications

### 4.2 Database Model Security
- **Password Hashing**: Stored as hash, not plain text
- **Unique Constraints**: Email is unique per user
- **Foreign Keys**: Enforce referential integrity
- **User IDs**: UUIDs used for user identification (not sequential)

### 4.3 Data Integrity
- Cascading deletes properly handle user-company associations
- Risk and company data is properly associated through foreign keys
- User deletion removes all associated data

---

## 5. User Data Protection

### 5.1 User Credentials
- Email addresses are lowercased for consistency
- Passwords are hashed with salt
- Password hashes are compared securely (not string comparison)

### 5.2 Session Data
- Minimal data stored in session: email, first_name, last_name, user_id
- No passwords or sensitive data in session
- Session data is updated when user changes profile information

### 5.3 Data Access Control
- Users can only access their own profile
- Users can only view their own companies and risks
- Profile page enforces user ID verification

---

## 6. Profile Page Security Features

### 6.1 User Profile Access (`/profile`)
- **Authentication Required**: Must be logged in
- **User Verification**: Confirms user ID matches session
- **CSRF Protection**: Form submissions verified
- **Actions Protected**:
  - Update personal information
  - Change password
  - Delete company associations

### 6.2 Personal Information Updates
- Email validation before update
- Check for duplicate emails (excluding current user)
- Input sanitization for names
- Database transaction with rollback on error

### 6.3 Password Change Security
- **Current Password Verification**: Must provide correct current password
- **Password Confirmation**: New password must match confirmation
- **Password Validation**: New password must meet strength requirements
- **Reuse Prevention**: Cannot reuse same password
- **Secure Hashing**: New password is hashed with salt

### 6.4 Company Association Deletion
- Removes only the user-company association
- Does not delete the company itself (admin-only operation)
- Confirmation dialog to prevent accidental deletion
- All user companies displayed with delete options

---

## 7. Security Best Practices Implemented

### 7.1 Secure Defaults
- Debug mode should be disabled in production (`debug=False`)
- Secret key should be changed in production environment
- Database connection strings should use environment variables

### 7.2 Error Handling
- User-friendly error messages (no stack traces)
- Server-side validation of all input
- Database transactions properly rolled back on errors
- Validation errors returned to user without exposing system details

### 7.3 Data Minimization
- Only necessary user data stored
- Session data limited to essential fields
- No sensitive data in URLs or logs
- Passwords never logged

### 7.4 Secure Coding Practices
- Type hints used for function parameters and returns
- Input validation before use
- Database transactions for data consistency
- Decorators for access control

---

## 8. Registration Security

### 8.1 Registration Process
1. Email validation
2. Input sanitization for names
3. Password strength validation
4. Check for duplicate email
5. Password hashing with salt and pepper
6. User creation in database
7. Automatic session creation (auto-login)

### 8.2 Registration Validation
- Email format and uniqueness checked
- First/last names sanitized
- Password meets minimum requirements
- All fields required
- Clear error messages for user feedback

---

## 9. Admin Tools Security

### 9.1 Admin Dashboard
- Admin-only access verified
- All admin routes protected with `@admin_required`
- Admin email hardcoded and verified

### 9.2 User Management (Admin)
- Admins can view all users
- Admins can update user information
- Admins can delete users
- Admins can merge user accounts
- All actions logged and verified

### 9.3 Company Management (Admin)
- Admins can view all companies
- Admins can create new companies
- Admins can update company information
- Admins can delete companies (also deletes associated risks)
- Non-admin users cannot perform these operations

---

## 10. Recommendations for Production Deployment

### 10.1 Environment Configuration
```bash
# Set these environment variables in production:
export FLASK_SECRET_KEY="<strong-random-key>"
export DATABASE_URL="<production-database-url>"
export OPENAI_API_KEY="<your-api-key-if-using-openai>"
export FLASK_ENV="production"
export LLM_MODE="mock"  # or "openai" if configured
```

### 10.2 Flask Configuration
```python
# Set in production:
app.debug = False
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
```

### 10.3 Database Security
- Use encrypted database connections (SSL/TLS)
- Regular database backups
- Restrict database access to application server only
- Use strong database passwords
- Enable database audit logging

### 10.4 HTTPS/TLS
- Use HTTPS only in production
- Obtain valid SSL/TLS certificate
- Implement HSTS headers
- Redirect HTTP to HTTPS

### 10.5 Logging & Monitoring
- Log all authentication attempts
- Monitor failed login attempts
- Alert on suspicious activity
- Keep application logs for audit trail
- Do not log passwords or sensitive data

### 10.6 Regular Security Audits
- Review access logs regularly
- Audit user permissions
- Check for inactive accounts
- Update dependencies for security patches
- Perform penetration testing

---

## 11. Known Limitations & Future Improvements

### 11.1 Current Limitations
- Admin email is hardcoded (should be database-managed)
- No multi-factor authentication (MFA)
- No password reset functionality
- Session timeout not enforced client-side
- No rate limiting on login attempts
- No IP-based access restrictions

### 11.2 Recommended Improvements
1. **Multi-Factor Authentication (MFA)**
   - TOTP (Time-based One-Time Password)
   - Email verification codes

2. **Password Reset Functionality**
   - Email-based password reset
   - Security questions
   - Token-based reset links

3. **Enhanced Logging**
   - Audit trail for all user actions
   - Failed login attempt tracking
   - Admin action logging

4. **Rate Limiting**
   - Limit login attempts
   - Prevent brute force attacks
   - Implement CAPTCHA

5. **Account Security**
   - Password history (prevent reuse)
   - Account lockout after failed attempts
   - Session management (show active sessions)
   - Device tracking

6. **Data Protection**
   - Encryption at rest
   - Encryption in transit (TLS)
   - Regular security audits
   - Penetration testing

---

## 12. Compliance & Standards

### 12.1 Security Standards Applied
- **OWASP Top 10** mitigation:
  - A01: Broken Access Control - Role-based access control implemented
  - A02: Cryptographic Failures - Passwords hashed, HTTPS recommended
  - A03: Injection - SQL injection prevented with ORM
  - A07: Cross-Site Scripting (XSS) - Input sanitization
  - A04: Insecure Design - Validation and authorization checks

- **CWE Coverage**:
  - CWE-79: Improper Neutralization of Input During Web Page Generation (XSS)
  - CWE-89: SQL Injection
  - CWE-256: Unprotected Storage of Credentials
  - CWE-287: Improper Authentication

---

## 13. Security Testing

### 13.1 Manual Testing Procedures
1. **Authentication Testing**
   - Attempt login with invalid credentials
   - Attempt access to protected pages without authentication
   - Verify session clears on logout

2. **Authorization Testing**
   - Attempt admin access as non-admin
   - Verify users can only access their own data
   - Confirm role-based restrictions

3. **Input Validation Testing**
   - Submit invalid email formats
   - Attempt SQL injection in form fields
   - Submit script tags in text fields
   - Test maximum length boundaries

4. **Password Security Testing**
   - Verify password hashing works
   - Test password validation rules
   - Confirm password comparison is secure

---

## 14. Contact & Support

For security concerns or vulnerabilities, please contact:
- Security Team: [contact information]
- Report vulnerabilities responsibly
- Do not disclose publicly until patched

---

## 15. Changelog

### Version 1.1 - Security Enhancements
- **Date**: April 4, 2026
- **Changes**:
  - Enhanced password requirements (8 characters, mixed case, numbers, special characters)
  - Added input validation and sanitization functions
  - Implemented user profile page with secure updates
  - Added company association deletion
  - Added password change functionality with current password verification
  - Enhanced email validation
  - Improved error handling and user feedback
  - Added role-based access control decorators
  - Documented all security measures

---

**Last Updated**: April 4, 2026
**Document Version**: 1.1
**Security Level**: Confidential
