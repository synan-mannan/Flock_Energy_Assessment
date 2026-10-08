from fastapi.testclient import TestClient

from app.api.meters import get_portal_client
from app.exceptions import (
    PortalAuthenticationError,
    PortalNotFoundError,
    PortalUnavailableError,
)
from app.main import create_app
from app.models.meter import (
    EnergyReading,
    Meter,
    MeterConsumption,
    MeterLocation,
    MeterSearchResult,
)


METER = Meter(
    meterId="J100001",
    serialNo="GE84132",
    make="L&T",
    phaseType="single",
    installStatus="Installed",
    dtCode="DT-002",
)


class FakePortal:
    def search_meters(self, query: str, page: int) -> MeterSearchResult:
        return MeterSearchResult(data=[METER], total=1, page=page, pageSize=20)

    def get_location(self, meter_id: str) -> MeterLocation:
        return MeterLocation(meterId=meter_id, latitude=26.82, longitude=75.90)

    def get_consumption(self, meter_id: str) -> MeterConsumption:
        return MeterConsumption(
            meterId=meter_id,
            readings=[EnergyReading(timestamp="2026-06-30T23:30:00", kwh="42.5", kvah="46.0", voltR="230")],
        )


def make_client(
    portal: object | None = None,
    *,
    raise_server_exceptions: bool = True,
) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_portal_client] = lambda: portal or FakePortal()
    return TestClient(application, raise_server_exceptions=raise_server_exceptions)


def test_health_does_not_contact_portal() -> None:
    class UnusedPortal:
        def search_meters(self, query: str, page: int) -> MeterSearchResult:
            raise AssertionError("health must not call the portal")

    with make_client(UnusedPortal()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_documents_health_meters_and_common_errors() -> None:
    with make_client() as client:
        schema = client.get("/openapi.json").json()

    assert schema["openapi"].startswith("3.")
    assert set(schema["paths"]) == {
        "/health",
        "/meters",
        "/meters/{meter_id}",
        "/meters/{meter_id}/location",
        "/meters/{meter_id}/consumption",
    }
    assert [item["name"] for item in schema["paths"]["/meters"]["get"]["parameters"]] == [
        "q",
        "page",
    ]
    assert schema["paths"]["/meters"]["get"]["responses"]["422"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/ApiError")


def test_search_meters_without_query_lists_first_page() -> None:
    with make_client() as client:
        response = client.get("/meters")

    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["data"][0]["meterId"] == "J100001"


def test_search_meters_returns_clean_response() -> None:
    with make_client() as client:
        response = client.get("/meters", params={"q": "J100001", "page": 1})

    assert response.status_code == 200
    assert response.json()["data"][0] == {
        "meterId": "J100001",
        "serialNo": "GE84132",
        "make": "L&T",
        "phaseType": "single",
        "installStatus": "Installed",
        "dtCode": "DT-002",
    }


def test_meter_details_returns_exact_search_match() -> None:
    with make_client() as client:
        response = client.get("/meters/J100001")

    assert response.status_code == 200
    assert response.json()["meterId"] == "J100001"


def test_location_returns_numeric_coordinates() -> None:
    with make_client() as client:
        response = client.get("/meters/J100001/location")

    assert response.status_code == 200
    assert response.json() == {
        "meterId": "J100001",
        "latitude": 26.82,
        "longitude": 75.9,
    }


def test_consumption_returns_energy_readings() -> None:
    with make_client() as client:
        response = client.get("/meters/J100001/consumption")

    assert response.status_code == 200
    assert response.json() == {
        "meterId": "J100001",
        "readings": [{
            "timestamp": "2026-06-30T23:30:00",
            "kwh": "42.5",
            "kvah": "46.0",
            "voltR": "230",
        }],
    }


def test_portal_authentication_error_is_sanitized() -> None:
    class UnauthorizedPortal(FakePortal):
        def search_meters(self, query: str, page: int) -> MeterSearchResult:
            raise PortalAuthenticationError("The portal rejected the configured credentials or session.")

    with make_client(UnauthorizedPortal()) as client:
        response = client.get("/meters")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert "cookie" not in response.text.lower()


def test_portal_failure_returns_service_unavailable() -> None:
    class UnavailablePortal(FakePortal):
        def search_meters(self, query: str, page: int) -> MeterSearchResult:
            raise PortalUnavailableError("The portal could not be reached.")

    with make_client(UnavailablePortal()) as client:
        response = client.get("/meters")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_invalid_page_returns_clean_validation_error() -> None:
    with make_client() as client:
        response = client.get("/meters?page=0")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PAGE"


def test_invalid_query_returns_clean_validation_error() -> None:
    with make_client() as client:
        response = client.get("/meters", params={"q": "x" * 101})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_QUERY"


def test_invalid_meter_id_returns_clean_validation_error() -> None:
    with make_client() as client:
        response = client.get("/meters/invalid%20id")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_METER_ID"


def test_unknown_meter_returns_not_found() -> None:
    class NoMatchPortal(FakePortal):
        def search_meters(self, query: str, page: int) -> MeterSearchResult:
            return MeterSearchResult(data=[], total=0, page=page, pageSize=20)

    with make_client(NoMatchPortal()) as client:
        response = client.get("/meters/J999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "METER_NOT_FOUND"


def test_unknown_location_returns_not_found() -> None:
    class MissingLocationPortal(FakePortal):
        def get_location(self, meter_id: str) -> MeterLocation:
            raise PortalNotFoundError("not found")

    with make_client(MissingLocationPortal()) as client:
        response = client.get("/meters/J999999/location")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "METER_NOT_FOUND"


def test_unknown_consumption_returns_not_found() -> None:
    class MissingConsumptionPortal(FakePortal):
        def get_consumption(self, meter_id: str) -> MeterConsumption:
            raise PortalNotFoundError("not found")

    with make_client(MissingConsumptionPortal()) as client:
        response = client.get("/meters/J999999/consumption")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "METER_NOT_FOUND"


def test_unexpected_internal_error_does_not_expose_details() -> None:
    class BrokenPortal(FakePortal):
        def search_meters(self, query: str, page: int) -> MeterSearchResult:
            raise RuntimeError("private internal detail")

    with make_client(BrokenPortal(), raise_server_exceptions=False) as client:
        response = client.get("/meters")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred.",
        }
    }
    assert "private internal detail" not in response.text