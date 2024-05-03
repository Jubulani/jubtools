from unittest import mock

import pytest

@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "env": "UnitTest",
        "request_ts": mock.ANY,
        "status": "UP",
        "uptime": mock.ANY,
        "version": "0.1.0",
    }