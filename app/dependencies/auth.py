from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService, InactiveUserError, InvalidCredentialsError

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Paste your access token from /login. Swagger will send it as a Bearer token.",
    auto_error=False,
)


def get_auth_service(db: Session = Depends(get_db_session)) -> AuthService:
    return AuthService(UserRepository(db))


def _invalid_credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _invalid_credentials_exception()

    try:
        return auth_service.get_current_user(credentials.credentials)
    except InvalidCredentialsError as exc:
        raise _invalid_credentials_exception() from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        ) from exc


def get_current_onboarded_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User account is missing a role; register with SELF or COACH",
        )
    return current_user


def get_current_coach(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User account is missing a role; register with SELF or COACH",
        )

    if current_user.role != UserRole.COACH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Coach role required",
        )
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User account is missing a role; register with SELF or COACH",
        )

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user