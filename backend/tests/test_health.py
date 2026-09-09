import pytest


@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Crypto-Tracer"
    assert data["status"] == "ONLINE"
    assert data["api_v1"] == "/api/v1"


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["app"] == "Crypto-Tracer"
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]


@pytest.mark.asyncio
async def test_mock_auth_endpoint(async_client):
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["is_authenticated"] is True
    assert "officer_id" in data
    assert "name" in data
    assert data["role"] == "INVESTIGATING_OFFICER"
