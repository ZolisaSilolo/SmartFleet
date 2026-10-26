"""
Tenant identity extraction for API Gateway HTTP API (payload format 2.0) with a JWT authorizer.

Security model (WA findings C1/C2):
  * The tenant comes ONLY from the verified Cognito ID-token claim `custom:tenantId`.
  * That attribute is immutable and not client-writable (see infrastructure/template.yaml),
    so a signed-in user cannot choose their own tenant.
  * Access tokens do not carry custom attributes, so an ID token is required (`token_use == "id"`).
  * There are NO development fallbacks (no header or default tenant): every environment,
    including local tests, must present claims in the same shape API Gateway produces.
"""
import re
from typing import Any, Dict, Tuple


class UnauthorizedException(Exception):
    """Raised when tenant or user identity cannot be established from verified claims."""


# Matches the tenant ids provisioned by the onboarding runbook (docs/RUNBOOKS.md).
TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")


def get_claims(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return the verified JWT claims injected by the API Gateway JWT authorizer (payload v2)."""
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    jwt = authorizer.get("jwt") or {}
    return jwt.get("claims") or {}


def get_tenant_id(event: Dict[str, Any]) -> str:
    claims = get_claims(event)
    if claims.get("token_use") != "id":
        raise UnauthorizedException("An ID token is required.")
    tenant = claims.get("custom:tenantId")
    if not isinstance(tenant, str) or not TENANT_ID_PATTERN.match(tenant):
        raise UnauthorizedException("Missing or invalid tenant authorization context.")
    return tenant


def get_user_id(event: Dict[str, Any]) -> str:
    claims = get_claims(event)
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise UnauthorizedException("Missing authenticated user context.")
    return user_id


def get_auth_context(event: Dict[str, Any]) -> Tuple[str, str]:
    """Returns (tenant_id, user_id)."""
    return get_tenant_id(event), get_user_id(event)
