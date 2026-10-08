import httpx
import pytest

from app.clients.urja_client import UrjaPortalClient
from app.config import Settings
from app.exceptions import PortalAuthenticationError, PortalUnavailableError


def test_search_logs_in_and_reuses_portal_session() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/login":
            return httpx.Response(
                200,
                headers={"set-cookie": "session=test-session; HttpOnly; Path=/"},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "data": [{
                    "meterId": "J100001",
                    "serialNo": "GE84132",
                    "make": "L&T",
                    "phaseType": "single",
                    "installStatus": "Installed",
                    "dtCode": "DT-002",
                }],
                "total": 1,
                "page": 1,
                "pageSize": 20,
            },
            request=request,
        )

    client = UrjaPortalClient(
        Settings(username="operator", password="secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.search_meters("J100001", 1)
    finally:
        client.close()

    assert [request.method for request in requests] == ["POST", "GET"]
    assert requests[0].url.path == "/login"
    assert requests[0].headers["origin"] == "https://urja-ops.flockenergy.tech"
    assert requests[0].headers["referer"] == "https://urja-ops.flockenergy.tech/login"
    assert requests[1].url.path == "/portal/meters/search"
    assert requests[1].headers["cookie"] == "session=test-session"
    assert result.data[0].meter_id == "J100001"
    assert result.page_size == 20


@pytest.mark.parametrize("expired_status", [401, 403])
def test_expired_portal_session_is_refreshed_and_retried(expired_status: int) -> None:
    requests: list[httpx.Request] = []
    login_count = 0
    portal_request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, portal_request_count
        requests.append(request)
        if request.url.path == "/login":
            login_count += 1
            return httpx.Response(
                200,
                headers={"set-cookie": f"session=session-{login_count}; HttpOnly; Path=/"},
                request=request,
            )
        portal_request_count += 1
        if portal_request_count == 1:
            return httpx.Response(expired_status, request=request)
        return httpx.Response(
            200,
            json={"data": [], "total": 0, "page": 1, "pageSize": 20},
            request=request,
        )

    client = UrjaPortalClient(
        Settings(username="operator", password="secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.search_meters("", 1)
    finally:
        client.close()

    assert result.total == 0
    assert login_count == 2
    assert portal_request_count == 2
    assert requests[1].headers["cookie"] == "session=session-1"
    assert requests[3].headers["cookie"] == "session=session-2"


def test_failed_retry_does_not_loop() -> None:
    login_count = 0
    portal_request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, portal_request_count
        if request.url.path == "/login":
            login_count += 1
            return httpx.Response(200, request=request)
        portal_request_count += 1
        return httpx.Response(401, request=request)

    client = UrjaPortalClient(
        Settings(username="operator", password="secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(PortalAuthenticationError):
            client.search_meters("", 1)
    finally:
        client.close()

    assert login_count == 2
    assert portal_request_count == 2


def test_failed_relogin_does_not_retry_protected_request() -> None:
    login_count = 0
    portal_request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, portal_request_count
        if request.url.path == "/login":
            login_count += 1
            return httpx.Response(200 if login_count == 1 else 403, request=request)
        portal_request_count += 1
        return httpx.Response(401, request=request)

    client = UrjaPortalClient(
        Settings(username="operator", password="secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(PortalAuthenticationError):
            client.search_meters("", 1)
    finally:
        client.close()

    assert login_count == 2
    assert portal_request_count == 1


def test_portal_server_error_raises_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login":
            return httpx.Response(200, request=request)
        return httpx.Response(500, request=request)

    client = UrjaPortalClient(
        Settings(username="operator", password="secret"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(PortalUnavailableError):
            client.search_meters("", 1)
    finally:
        client.close()


def test_blank_base_url_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URJA_BASE_URL", "")

    assert Settings().base_url == "https://urja-ops.flockenergy.tech"