"""
Google OAuth 2.0 configuration and utilities
Secure OAuth implementation using Authlib
"""
import os
from authlib.integrations.flask_client import OAuth
from flask import url_for


def init_oauth(app):
    """
    Initialize OAuth with Google provider

    Required environment variables:
    - GOOGLE_CLIENT_ID: Google OAuth client ID
    - GOOGLE_CLIENT_SECRET: Google OAuth client secret
    """
    oauth = OAuth(app)

    # Get OAuth credentials from environment
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    if not client_id or not client_secret:
        app.logger.warning("Google OAuth not configured: Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")
        return None

    # Register Google OAuth provider
    google = oauth.register(
        name='google',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile',
            'prompt': 'select_account',  # Force account selection
        }
    )

    app.logger.info("Google OAuth configured successfully")
    return oauth


def get_redirect_uri(request):
    """
    Get the appropriate redirect URI based on environment

    Returns:
        str: Full redirect URI for OAuth callback
    """
    # Check if we're in production (Render.com)
    if request.host.startswith('dcabot-saas-web.onrender.com'):
        return 'https://dcabot-saas-web.onrender.com/auth/google/callback'

    # Local development
    return url_for('google_callback', _external=True)


def extract_user_info(token):
    """
    Extract user information from Google OAuth token

    Args:
        token: OAuth token response

    Returns:
        dict: User information (id, email, name, picture)
    """
    userinfo = token.get('userinfo', {})

    return {
        'google_id': userinfo.get('sub'),  # Google user ID
        'email': userinfo.get('email'),
        'email_verified': userinfo.get('email_verified', False),
        'name': userinfo.get('name'),
        'picture': userinfo.get('picture'),
        'given_name': userinfo.get('given_name'),
        'family_name': userinfo.get('family_name'),
    }
