from app.clients.urja_client import UrjaPortalClient
from app.exceptions import PortalNotFoundError
from app.models.meter import Meter, MeterConsumption, MeterLocation, MeterSearchResult


class MeterService:
    def __init__(self, portal: UrjaPortalClient) -> None:
        self._portal = portal

    def search(self, query: str, page: int) -> MeterSearchResult:
        return self._portal.search_meters(query, page)

    def get_meter(self, meter_id: str) -> Meter:
        result = self._portal.search_meters(meter_id, page=1)
        meter = next((item for item in result.data if item.meter_id == meter_id), None)
        if meter is None:
            raise PortalNotFoundError("The requested meter was not found in the portal.")
        return meter

    def get_location(self, meter_id: str) -> MeterLocation:
        return self._portal.get_location(meter_id)

    def get_consumption(self, meter_id: str) -> MeterConsumption:
        return self._portal.get_consumption(meter_id)