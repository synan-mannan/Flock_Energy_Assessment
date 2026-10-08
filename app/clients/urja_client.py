from threading import Lock
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.exceptions import (
    PortalAuthenticationError,
    PortalConfigurationError,
    PortalNotFoundError,
    PortalTimeoutError,
    PortalUnavailableError,
    UnexpectedPortalResponseError,
)
from app.models.meter import (
    EnergyReading,
    Meter,
    MeterConsumption,
    MeterLocation,
    MeterSearchResult,
)


class UrjaPortalClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url.rstrip("/"),
            timeout=settings.timeout_seconds,
            follow_redirects=True,
            transport=transport,
        )
        self._authenticated = False
        self._auth_lock = Lock()

    def close(self) -> None:
        self._client.close()

    def search_meters(self, query: str, page: int) -> MeterSearchResult:
        payload = self._get_json("/portal/meters/search", params={"q": query, "page": page})
        return self._parse(MeterSearchResult, payload)

    def get_meter(self, meter_id: str) -> Meter | None:
        result = self.search_meters(meter_id, page=1)
        return next((meter for meter in result.data if meter.meter_id == meter_id), None)

    def get_location(self, meter_id: str) -> MeterLocation:
        payload = self._get_json(f"/portal/meters/{meter_id}/geo")
        data = self._require_data(payload, dict)
        return self._parse(MeterLocation, {"meterId": meter_id, **data})

    def get_consumption(self, meter_id: str) -> MeterConsumption:
        payload = self._get_json(f"/portal/meters/{meter_id}/energy")
        readings = self._require_data(payload, list)
        return self._parse(
            MeterConsumption,
            {
                "meterId": meter_id,
                "readings": [self._parse(EnergyReading, reading) for reading in readings],
            },
        )

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        self._ensure_authenticated()
        response = self._request("GET", path, params=params)
        if response.status_code in (401, 403):
            self._reauthenticate()
            response = self._request("GET", path, params=params)
        self._raise_for_status(response)
        try:
            return response.json()
        except ValueError as exc:
            raise UnexpectedPortalResponseError("The portal returned an invalid response.") from exc

    def _ensure_authenticated(self) -> None:
        with self._auth_lock:
            if self._authenticated:
                return
            self._login()

    def _reauthenticate(self) -> None:
        with self._auth_lock:
            self._authenticated = False
            self._client.cookies.clear()
            self._login()

    def _login(self) -> None:
        if not self._settings.username or not self._settings.password:
            raise PortalConfigurationError("Portal credentials are not configured.")
        response = self._request(
            "POST",
            "/login",
            data={"email": self._settings.username, "password": self._settings.password},
            headers={
                "Origin": self._settings.base_url.rstrip("/"),
                "Referer": f"{self._settings.base_url.rstrip('/')}/login",
            },
            authentication_request=True,
        )
        if response.status_code >= 400:
            self._raise_for_status(response, authentication_request=True)
        self._authenticated = True

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        authentication_request: bool = False,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, params=params, data=data, headers=headers)
        except httpx.TimeoutException as exc:
            raise PortalTimeoutError("The portal request timed out.") from exc
        except httpx.RequestError as exc:
            raise PortalUnavailableError("The portal could not be reached.") from exc

        if authentication_request:
            self._raise_for_status(response, authentication_request=True)
        return response

    def _raise_for_status(
        self,
        response: httpx.Response,
        *,
        authentication_request: bool = False,
    ) -> None:
        if response.status_code == 401 or response.status_code == 403:
            self._authenticated = False
            raise PortalAuthenticationError("The portal rejected the configured credentials or session.")
        if response.status_code == 404:
            raise PortalNotFoundError("The requested meter was not found in the portal.")
        if response.status_code >= 500:
            raise PortalUnavailableError("The portal returned a server error.")
        if response.status_code >= 400:
            raise UnexpectedPortalResponseError("The portal rejected the request.")

    @staticmethod
    def _require_data(payload: Any, expected_type: type) -> Any:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), expected_type):
            raise UnexpectedPortalResponseError("The portal returned an unexpected response.")
        return payload["data"]

    @staticmethod
    def _parse(model: type, payload: Any) -> Any:
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise UnexpectedPortalResponseError("The portal returned an unexpected response.") from exc