"""
Authentication and Authorization service for fit-jwt-py.
All JWT/OAuth details are isolated here.
"""
import ast
import logging
import os
from typing import Optional

import fitjwtpy
from flask import make_response, redirect

logger = logging.getLogger(__name__)


def init_authnz() -> None:
    """Initialize fit-jwt-py with OAuth configuration."""
    try:
        fitjwtpy.init()
    except Exception:
        logger.warning("fit-jwt-py initialization failed", exc_info=True)
        raise


def get_user_from_token(token: str) -> Optional[dict]:
    """Validate token and extract user info."""
    user_info = fitjwtpy.get_user_from_token(token)
    if not user_info:
        return None
    return {
        "oidc_user_id": user_info.get("sub"),
        "email": user_info.get("email"),
        "first_name": user_info.get("given_name", ""),
        "last_name": user_info.get("family_name", ""),
        "username": user_info.get("preferred_username"),
    }


def get_user_from_auth_header(auth_header: Optional[str]) -> Optional[dict]:
    """Extract token from Authorization header and return user info."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    return get_user_from_token(token)


def build_login_response(cookie_name: str, max_age: int = 600):
    """Create the OAuth login redirect response with PKCE cookie set."""
    pkce_details = fitjwtpy.get_pkce_details("S256")
    auth_url = fitjwtpy.get_auth_url(pkce_details)

    response = make_response(redirect(auth_url))
    cookie_value = {
        "codeVerifier": pkce_details.code_verifier,
        "codeChallenge": pkce_details.code_challenge,
        "method": pkce_details.method,
    }
    response.set_cookie(
        key=cookie_name,
        value=str(cookie_value),
        httponly=True,
        max_age=max_age,
    )
    return response


def exchange_code_for_tokens_from_cookie(code: str, raw_cookie: str):
    """Exchange authorization code for tokens using PKCE cookie contents."""
    pkce_details = ast.literal_eval(raw_cookie)
    return fitjwtpy.get_jwt_token(code, pkce_details["codeVerifier"])


def refresh_token(token: str):
    """Refresh a JWT token."""
    return fitjwtpy.refresh_jwt_token(token)


def get_logout_url(redirect_uri: str) -> str:
    """Build the OIDC logout URL."""
    token_endpoint = os.getenv("TOKEN_ENDPOINT", "")
    logout_endpoint = token_endpoint.replace("/token", "/logout")
    return f"{logout_endpoint}?redirect_uri={redirect_uri}"
