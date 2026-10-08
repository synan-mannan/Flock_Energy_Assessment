from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.meters import router
from app.clients.urja_client import UrjaPortalClient
from app.config import Settings
from app.exceptions import (
    PortalAuthenticationError,
    PortalConfigurationError,
    PortalError,
    PortalNotFoundError,
    PortalTimeoutError,
    PortalUnavailableError,
    UnexpectedPortalResponseError,
)
from app.models.meter import ApiError, ApiErrorDetail, HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        portal = UrjaPortalClient(configuration)
        application.state.portal_client = portal
        try:
            yield
        finally:
            portal.close()

    application = FastAPI(
        title="Urja Meter API",
        description="A small REST API for verified meter data available from Urja Meter Ops.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(router)

    @application.get(
        "/health",
        response_model=HealthResponse,
        responses={500: {"model": ApiError, "description": "Unexpected internal error"}},
        tags=["health"],
        summary="Check API health",
        description="Returns API process health without contacting the Urja portal.",
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    @application.exception_handler(PortalError)
    async def handle_portal_error(request: Request, exc: PortalError) -> JSONResponse:
        if isinstance(exc, PortalNotFoundError):
            status_code, code, message = 404, "METER_NOT_FOUND", "Meter was not found."
        elif isinstance(exc, PortalTimeoutError):
            status_code, code, message = 504, "UPSTREAM_ERROR", "The portal request timed out."
        elif isinstance(exc, PortalUnavailableError):
            status_code, code, message = 503, "UPSTREAM_ERROR", "The portal is unavailable."
        elif isinstance(exc, PortalConfigurationError):
            status_code, code, message = 503, "UPSTREAM_ERROR", "Portal credentials are not configured."
        elif isinstance(exc, (PortalAuthenticationError, UnexpectedPortalResponseError)):
            status_code, code, message = 502, "UPSTREAM_ERROR", "The portal request failed."
        else:
            status_code, code, message = 502, "UPSTREAM_ERROR", "The portal request failed."
        return JSONResponse(
            status_code=status_code,
            content=ApiError(error=ApiErrorDetail(code=code, message=message)).model_dump(),
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        locations = {str(part) for error in exc.errors() for part in error.get("loc", ())}
        if "page" in locations:
            code, message = "INVALID_PAGE", "page must be a positive integer."
        elif "q" in locations:
            code, message = "INVALID_QUERY", "q must be no longer than 100 characters."
        elif "meter_id" in locations:
            code, message = "INVALID_METER_ID", "meter_id contains invalid characters."
        else:
            code, message = "INVALID_REQUEST", "Request parameters are invalid."
        return JSONResponse(
            status_code=422,
            content=ApiError(error=ApiErrorDetail(code=code, message=message)).model_dump(),
        )

    @application.exception_handler(Exception)
    async def handle_internal_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ApiError(
                error=ApiErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An internal error occurred.",
                )
            ).model_dump(),
        )

    return application


app = create_app()