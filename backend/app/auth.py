"""Authentication dependencies and OpenAPI security scheme."""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from backend.app.config import get_settings

# Declare X-Authority-Key security scheme so it renders in OpenAPI schema
authority_key_header = APIKeyHeader(
    name="X-Authority-Key",
    scheme_name="AuthorityApiKey",
    auto_error=False,
    description="Pre-shared administrative key for disaster management authority endpoints",
)


async def verify_authority_key(api_key: str = Security(authority_key_header)) -> str:
    """Validate incoming X-Authority-Key against server configuration."""
    settings = get_settings()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required header: X-Authority-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if api_key != settings.authority_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Authority-Key credentials",
        )
    return api_key
