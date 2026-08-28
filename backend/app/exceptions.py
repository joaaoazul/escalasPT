"""
Custom exception handlers for consistent API error responses.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.utils.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        status_code: int = 500,
        detail: str = "Internal server error",
        error_code: str = "INTERNAL_ERROR",
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


class AuthenticationError(AppException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTH_ERROR",
        )


class AuthorizationError(AppException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="FORBIDDEN",
        )


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource", detail: str | None = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{resource} not found",
            error_code="NOT_FOUND",
        )


class ConflictError(AppException):
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="CONFLICT",
        )


class ValidationError(AppException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="VALIDATION_ERROR",
        )


class RateLimitError(AppException):
    def __init__(self, detail: str = "Too many requests"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            error_code="RATE_LIMITED",
        )


class TOTPRequiredError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TOTP verification required",
            error_code="TOTP_REQUIRED",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "AppException: status=%s code=%s detail=%s path=%s",
            exc.status_code,
            exc.error_code,
            exc.detail,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        # OWASP ASVS V13: in production, strip internal location details from validation errors
        from app.config import get_settings
        settings = get_settings()
        if settings.APP_DEBUG:
            error_detail = jsonable_encoder(exc.errors())
        else:
            # Only return field name and message, not internal loc/type/ctx
            error_detail = [
                {"field": ".".join(str(loc) for loc in e.get("loc", [])), "msg": e.get("msg", "")}
                for e in exc.errors()
            ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "detail": "Request validation failed",
                "errors": error_detail,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "detail": "An unexpected error occurred",
            },
        )
