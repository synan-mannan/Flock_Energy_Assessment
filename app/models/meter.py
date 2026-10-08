from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})

    status: Literal["ok"] = "ok"


class ApiErrorDetail(BaseModel):
    code: str
    message: str


class ApiError(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "METER_NOT_FOUND",
                    "message": "Meter was not found.",
                }
            }
        }
    )

    error: ApiErrorDetail


class Meter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meter_id: str = Field(alias="meterId")
    serial_no: str = Field(alias="serialNo")
    make: str
    phase_type: str = Field(alias="phaseType")
    install_status: str = Field(alias="installStatus")
    dt_code: str = Field(alias="dtCode")


class MeterSearchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data: list[Meter]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


class MeterLocation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meter_id: str = Field(alias="meterId")
    latitude: float
    longitude: float


class EnergyReading(BaseModel):
    timestamp: str
    kwh: str
    kvah: str
    voltR: str


class MeterConsumption(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meter_id: str = Field(alias="meterId")
    readings: list[EnergyReading]