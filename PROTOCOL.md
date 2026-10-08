# Urja Portal Protocol

## Verified

### Authentication

The portal accepts a `POST /login` form with `email` and `password`; the observed form had no hidden CSRF input. A bare form POST returned 403, while submitting with `Origin: https://urja-ops.flockenergy.tech` and `Referer: https://urja-ops.flockenergy.tech/login` succeeded. Protected requests worked after login. After sign-out, a protected request returned HTTP 401 with `error: "unauthorized"` and `message: "A valid session is required."`

### Meter search

`GET /portal/meters/search?q={query}&page={page}` searches by meter ID or serial number. An empty query lists meters. The JSON response contains `data`, `total`, `page`, and `pageSize`; meter fields are `meterId`, `serialNo`, `make`, `phaseType`, `installStatus`, and `dtCode`. The observed dataset had 403 meters and 20 results per page.

### Location and energy

`GET /portal/meters/{meter_id}/geo` returns `data.latitude` and `data.longitude` as strings.

`GET /portal/meters/{meter_id}/energy` returns a `data` array with `timestamp`, `kwh`, `kvah`, and `voltR` string fields. The inspected meter had 337 records at half-hour intervals. No date filters or pagination were observed on this request.

### Transformers and export

`GET /portal/dts?page={page}` returns paginated transformer records with `code`, `name`, `feederCode`, and `capacityKva`.

The portal UI's export action requested `/portal/keys` and `/portal/export?page=1`. A direct unsigned request to the export endpoint returned `401 signature_invalid`.

## Unknown / Not Verified

- The exact session cookie/token semantics and session expiration duration were not established.
- The energy fields' measurement semantics and the portal timestamps' timezone were not established.
- The export signing flow and `/portal/keys` response were not investigated.
- Some detail-page fields and the displayed network hierarchy were not available through the verified data endpoints.

## API Client Policy (Not a Portal Guarantee)

The service retains one HTTP client. After a data request returns 401 or 403, it clears the local client cookie jar, logs in again with the observed form request, and retries that data request once. This is service recovery behavior; the portal's expiration policy remains unknown.
