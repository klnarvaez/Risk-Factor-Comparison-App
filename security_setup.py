#!/usr/bin/env python3
"""
Security Setup Script for Risk Factor Comparison App

This script generates secure credentials and manages the .env file.
It creates a cryptographically secure Flask SECRET_KEY and other sensitive configurations.

Usage:
    python security_setup.py
    python security_setup.py --regenerate  # Force regeneration of existing keys
"""

import os
import sys
import secrets
import argparse
from pathlib import Path
from typing import Dict, Optional


class SecuritySetup:
    """Manages secure credential generation and .env file management."""
    
    ENV_FILE = ".env"
    PROJECT_ROOT = Path(__file__).parent
    
    def __init__(self, force_regenerate: bool = False):
        """
        Initialize the security setup.
        
        Args:
            force_regenerate: If True, regenerate all keys even if they exist.
        """
        self.force_regenerate = force_regenerate
        self.env_path = self.PROJECT_ROOT / self.ENV_FILE
        self.env_vars: Dict[str, str] = {}
        self._load_existing_env()
    
    def _load_existing_env(self) -> None:
        """Load existing .env file if it exists."""
        if self.env_path.exists():
            with open(self.env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        self.env_vars[key.strip()] = value.strip()
    
    @staticmethod
    def generate_secret_key(length: int = 32) -> str:
        """
        Generate a cryptographically secure Flask secret key.
        
        Args:
            length: Length of the secret key in bytes (default: 32, generates 64 hex chars)
        
        Returns:
            A secure random hex string suitable for Flask SECRET_KEY.
        """
        return secrets.token_hex(length)
    
    @staticmethod
    def generate_api_key(prefix: str = "", length: int = 32) -> str:
        """
        Generate a cryptographically secure API key.
        
        Args:
            prefix: Optional prefix for the API key (e.g., "sk_" for secret keys)
            length: Length of the key in bytes (default: 32)
        
        Returns:
            A secure random API key.
        """
        key = secrets.token_urlsafe(length)
        return f"{prefix}{key}" if prefix else key
    
    def setup_flask_secret_key(self) -> str:
        """
        Setup or retrieve the Flask SECRET_KEY.
        
        Returns:
            The Flask SECRET_KEY value.
        """
        key_name = "FLASK_SECRET_KEY"
        
        if key_name in self.env_vars and not self.force_regenerate:
            print(f"✓ Flask SECRET_KEY already exists (use --regenerate to overwrite)")
            return self.env_vars[key_name]
        
        secret_key = self.generate_secret_key()
        self.env_vars[key_name] = secret_key
        print(f"✓ Generated new Flask SECRET_KEY")
        return secret_key
    
    def setup_database_url(self, db_url: Optional[str] = None) -> str:
        """
        Setup or retrieve the database URL.
        
        Args:
            db_url: Optional database URL to set. If None and not in .env, prompts user.
        
        Returns:
            The database URL.
        """
        key_name = "DATABASE_URL"
        
        if key_name in self.env_vars and not self.force_regenerate and not db_url:
            return self.env_vars[key_name]
        
        if db_url:
            self.env_vars[key_name] = db_url
            print(f"✓ Set DATABASE_URL")
            return db_url
        
        if key_name not in self.env_vars:
            print("\n⚠ DATABASE_URL not configured.")
            print("  Example: postgresql://user:password@localhost/dbname")
            db_url = input("  Enter your database URL (or press Enter to skip): ").strip()
            if db_url:
                self.env_vars[key_name] = db_url
                print(f"✓ Set DATABASE_URL")
            return db_url
        
        return self.env_vars[key_name]
    
    def setup_flask_env(self, env: str = "production") -> str:
        """
        Setup the Flask environment.
        
        Args:
            env: Environment type ('development', 'production', 'testing')
        
        Returns:
            The Flask environment.
        """
        key_name = "FLASK_ENV"
        valid_envs = ("development", "production", "testing")
        
        if env not in valid_envs:
            raise ValueError(f"Invalid environment. Must be one of: {valid_envs}")
        
        self.env_vars[key_name] = env
        print(f"✓ Set FLASK_ENV to '{env}'")
        return env
    
    def save_env_file(self) -> bool:
        """
        Save the environment variables to .env file.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            with open(self.env_path, 'w') as f:
                f.write("# Risk Factor Comparison App - Environment Configuration\n")
                f.write("# IMPORTANT: Never commit this file to version control!\n")
                f.write("# IMPORTANT: Add .env to .gitignore\n\n")
                
                for key, value in self.env_vars.items():
                    # Quote values that contain spaces or special characters
                    if ' ' in value or '=' in value:
                        f.write(f'{key}="{value}"\n')
                    else:
                        f.write(f'{key}={value}\n')
            
            print(f"\n✓ Environment variables saved to {self.env_path}")
            return True
        
        except IOError as e:
            print(f"\n✗ Error saving .env file: {e}", file=sys.stderr)
            return False
    
    def display_summary(self) -> None:
        """Display a summary of configured environment variables."""
        print("\n" + "=" * 60)
        print("Environment Configuration Summary")
        print("=" * 60)
        
        for key in sorted(self.env_vars.keys()):
            # Don't display full secret keys for security
            value = self.env_vars[key]
            if "SECRET" in key or "KEY" in key:
                display_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
            elif "PASSWORD" in key or "TOKEN" in key:
                display_value = "***"
            else:
                display_value = value
            
            print(f"  {key}: {display_value}")
        
        print("=" * 60)
    
    def run_interactive_setup(self) -> bool:
        """
        Run an interactive setup wizard.
        
        Returns:
            True if setup completed successfully.
        """
        print("\n" + "=" * 60)
        print("Risk Factor Comparison App - Security Setup")
        print("=" * 60)
        
        # Setup Flask SECRET_KEY
        print("\n[1/3] Configuring Flask SECRET_KEY...")
        self.setup_flask_secret_key()
        
        # Setup Database URL
        print("\n[2/3] Configuring Database URL...")
        self.setup_database_url()
        
        # Setup Flask Environment
        print("\n[3/3] Configuring Flask Environment...")
        env = input("Enter Flask environment (development/production/testing) [production]: ").strip()
        self.setup_flask_env(env if env else "production")
        
        # Display summary
        self.display_summary()
        
        # Save to file
        print("\nSaving configuration...")
        if self.save_env_file():
            print("\n✓ Security setup completed successfully!")
            print("\nNext steps:")
            print("  1. Review the .env file to ensure all values are correct")
            print("  2. Add .env to your .gitignore if not already present")
            print("  3. Update your Flask app to load these variables:")
            print("     from dotenv import load_dotenv")
            print("     load_dotenv()")
            return True
        
        return False


def main():
    """Main entry point for the security setup script."""
    parser = argparse.ArgumentParser(
        description="Security setup script for Risk Factor Comparison App"
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate all security keys (overwrites existing .env)"
    )
    parser.add_argument(
        "--flask-env",
        choices=["development", "production", "testing"],
        default="production",
        help="Set Flask environment (default: production)"
    )
    parser.add_argument(
        "--db-url",
        help="Set database URL directly"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run setup without interactive prompts"
    )
    
    args = parser.parse_args()
    
    try:
        setup = SecuritySetup(force_regenerate=args.regenerate)
        
        if args.non_interactive:
            # Non-interactive mode
            setup.setup_flask_secret_key()
            setup.setup_flask_env(args.flask_env)
            if args.db_url:
                setup.setup_database_url(args.db_url)
            setup.display_summary()
            return 0 if setup.save_env_file() else 1
        else:
            # Interactive mode
            return 0 if setup.run_interactive_setup() else 1
    
    except Exception as e:
        print(f"\n✗ Setup failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
