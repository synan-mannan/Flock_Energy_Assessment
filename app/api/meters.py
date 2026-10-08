from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from app.clients.urja_client import UrjaPortalClient
from app.models.meter import ApiError, Meter, MeterConsumption, MeterLocation, MeterSearchResult
from app.services.meter_service import MeterService

router = APIRouter(tags=["meters"])

ERROR_RESPONSES = {
    404: {"model": ApiError, "description": "Meter not found"},
    422: {"model": ApiError, "description": "Invalid request parameters"},
    502: {"model": ApiError, "description": "Portal authentication or response failure"},
    503: {"model": ApiError, "description": "Portal unavailable or credentials not configured"},
    504: {"model": ApiError, "description": "Portal request timed out"},
    500: {"model": ApiError, "description": "Unexpected internal error"},
}


def get_portal_client(request: Request) -> UrjaPortalClient:
    return request.app.state.portal_client


def get_meter_service(
    portal: Annotated[UrjaPortalClient, Depends(get_portal_client)],
) -> MeterService:
    return MeterService(portal)


MeterId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Meter identifier from the portal.",
        examples=["J100001"],
    ),
]


@router.get(
    "/meters",
    response_model=MeterSearchResult,
    responses=ERROR_RESPONSES,
    summary="Search meters",
    description="Search the portal by meter ID or serial number. An empty query lists meters.",
)
def search_meters(
    service: Annotated[MeterService, Depends(get_meter_service)],
    q: Annotated[
        str,
        Query(max_length=100, description="Meter ID or serial number; empty lists the first page."),
    ] = "",
    page: Annotated[int, Query(ge=1, description="One-based page number.")] = 1,
) -> MeterSearchResult:
    return service.search(q, page)


@router.get(
    "/meters/{meter_id}",
    response_model=Meter,
    responses=ERROR_RESPONSES,
    summary="Get meter details",
    description="Return the meter fields available from the portal search endpoint.",
)
def get_meter(
    meter_id: MeterId,
    service: Annotated[MeterService, Depends(get_meter_service)],
) -> Meter:
    return service.get_meter(meter_id)


@router.get(
    "/meters/{meter_id}/location",
    response_model=MeterLocation,
    responses=ERROR_RESPONSES,
    summary="Get meter location",
    description="Return the meter coordinates provided by the portal.",
)
def get_location(
    meter_id: MeterId,
    service: Annotated[MeterService, Depends(get_meter_service)],
) -> MeterLocation:
    return service.get_location(meter_id)


@router.get(
    "/meters/{meter_id}/consumption",
    response_model=MeterConsumption,
    responses=ERROR_RESPONSES,
    summary="Get meter energy readings",
    description="Return the energy readings provided by the portal without date filtering or pagination.",
)
def get_consumption(
    meter_id: MeterId,
    service: Annotated[MeterService, Depends(get_meter_service)],
) -> MeterConsumption:
    return service.get_consumption(meter_id)