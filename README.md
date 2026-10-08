# Urja Meter API

A read-only FastAPI service that exposes verified meter data from the Urja Meter Ops portal through a small REST API.

## Architecture

```text
Client
  |
  v
FastAPI
  |
  v
Meter Service
  |
  v
Urja Portal Client
  |
  v
Urja Meter Ops
```

FastAPI validates requests and formats responses. The meter service handles meter lookup. The portal client owns login, session reuse, and one-time session recovery. Urja Meter Ops remains the data source.

## Features

- Meter search/listing, meter details, location, and energy readings.
- Portal login through environment-configured credentials and persistent session reuse.
- One re-login and retry after an authenticated portal request returns 401 or 403.
- Request validation and consistent, sanitized JSON errors.
- Health endpoint that does not call the portal.
- FastAPI OpenAPI/Swagger documentation and mocked automated tests.

## API

| Method | Endpoint                         | Description                                  |
| ------ | -------------------------------- | -------------------------------------------- |
| GET    | `/health`                        | API process health                           |
| GET    | `/meters`                        | Search/list meters; accepts `q` and `page`   |
| GET    | `/meters/{meter_id}`             | Meter fields available through portal search |
| GET    | `/meters/{meter_id}/location`    | Numeric latitude and longitude               |
| GET    | `/meters/{meter_id}/consumption` | Portal energy readings                       |

```sh
curl "http://127.0.0.1:8000/meters?q=J100001&page=1"
curl "http://127.0.0.1:8000/meters/J100001/location"
```

Example location response:

```json
{ "meterId": "J100001", "latitude": 26.8221, "longitude": 75.9072 }
```

Example error response:

```json
{ "error": { "code": "METER_NOT_FOUND", "message": "Meter was not found." } }
```

## Authentication

Set `URJA_BASE_URL`, `URJA_USERNAME`, and `URJA_PASSWORD` in the environment. The API logs into the portal internally and reuses one HTTP client. An upstream 401 or 403 clears the current client session, logs in again using the observed same-origin form request, and retries the original read once. API responses never contain portal credentials or session values. The exact portal cookie/session mechanism is not assumed.

## Error Handling

Errors use `{"error":{"code":"...","message":"..."}}`. `INVALID_PAGE`, `INVALID_QUERY`, and `INVALID_METER_ID` return 422; `METER_NOT_FOUND` returns 404; `UPSTREAM_ERROR` uses 502, 503, or 504 depending on the upstream failure; unexpected errors return 500 with `INTERNAL_ERROR` and a generic message.

## Testing

Run `python -m pytest`. Tests use mocked portal responses and do not require live credentials. They cover route results, input validation, error sanitization, upstream failures, session reuse, recovery after 401/403, and the bounded retry failure case.

## Setup

Requires Python 3.10 or newer.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure `URJA_BASE_URL`, `URJA_USERNAME`, `URJA_PASSWORD`, and optional `URJA_TIMEOUT_SECONDS` (default `10`) in `.env`. `.env` is ignored by Git and must never be committed.

## Run

```sh
uvicorn app.main:app --reload
```

Open Swagger UI at <http://127.0.0.1:8000/docs>.

## OpenAPI

FastAPI serves the generated OpenAPI 3.x schema at `/openapi.json`; the checked-in copy is [`openapi.json`](openapi.json).

## Project Structure

```text
app/api/meters.py              Meter routes and request validation
app/clients/urja_client.py     Portal login, session, requests, and parsing
app/config.py                  Environment configuration
app/exceptions.py              Portal error types
app/main.py                    FastAPI setup and common error handlers
app/models/meter.py            API and portal response models
app/services/meter_service.py  Meter lookup logic
tests/test_api.py              Mocked API route/error tests
tests/test_urja_client.py      Mocked portal session/client tests
PROTOCOL.md                    Portal investigation findings
REFLECTION.md                  Assessment reflection
```

## Assumptions and Trade-offs

Observed portal response shapes are treated as the current contract. Session expiry is detected through 401/403 and retried once. Coordinates are numeric; energy fields and timestamps remain strings because their meaning/timezone was not confirmed. The service queries the portal directly, with no database or cache, so availability depends on the portal.

Bulk export, full dataset indexing, network hierarchy reconstruction, a frontend, and advanced monitoring are intentionally skipped. See [`PROTOCOL.md`](PROTOCOL.md) for verified and unknown portal behavior and [`REFLECTION.md`](REFLECTION.md) for the implementation reflection.
