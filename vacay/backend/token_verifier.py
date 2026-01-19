#!/usr/bin/env python3
"""
OAuth/OIDC Authentication Middleware for MCP Server

Implements token verification using fit-jwt-py library to secure MCP calculator endpoints.
Follows MCP OAuth specification for Resource Server (RS) implementation.
"""

import os
import logging
from typing import Optional
from fitjwtpy import get_user_from_token
from mcp.server.auth.provider import AccessToken, TokenVerifier


logger = logging.getLogger(__name__)


class JWTTokenVerifier(TokenVerifier):
    
    def __init__(
        self,
        issuer: str,
        audience: str
    ):
        self.issuer = issuer
        self.audience = audience
    
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            # Use fit-jwt-py to validate and extract user info
            # This validates signature, issuer, expiration, and returns decoded payload
            user_info = get_user_from_token(token)
            if not user_info:
                logger.warning("Token validation failed")
                return None
            
            # Custom audience validation for access tokens
            # (fit-jwt-py only validates audience for id_token, not access_token)
            token_audience = user_info.get('aud')
            audience_valid = (
                token_audience == self.audience if isinstance(token_audience, str)
                else self.audience in token_audience if isinstance(token_audience, list)
                else False
            )
            if not audience_valid:
                logger.warning(
                    "Token audience validation failed. Expected=%s Got=%s",
                    self.audience,
                    token_audience,
                )
                return None

            # Extract scopes
            token_scopes = []
            scope_claim = user_info.get("scope")
            if isinstance(scope_claim, str):
                token_scopes = scope_claim.split()
            elif isinstance(scope_claim, list):
                token_scopes = scope_claim
            
            # Extract client_id (azp or aud, preferring azp)
            client_id = user_info.get("azp") or token_audience
            if isinstance(client_id, list):
                client_id = client_id[0]
            
            # Return AccessToken with MCP SDK fields
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=token_scopes,
                expires_at=user_info.get("exp")
            )
            
        except Exception as e:
            logger.exception("Token verification failed")
            return None


def create_token_verifier_from_env() -> Optional[JWTTokenVerifier]:

    jwks_url = os.getenv("JWKS_URL")
    issuer = os.getenv("OAUTH_ISSUER")
    audience = os.getenv("OAUTH_AUDIENCE")
    client_id = os.getenv("CLIENT_ID")
    
    if not all([jwks_url, issuer, audience, client_id]):
        logger.warning(
            "OAuth not configured. Set JWKS_URL, OAUTH_ISSUER, OAUTH_AUDIENCE, and CLIENT_ID environment variables."
        )
        return None
    
    return JWTTokenVerifier(
        issuer=issuer,
        audience=audience
    )
