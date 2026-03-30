from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.mock_db import get_mock_collection, reset_mock_db


@pytest.fixture(autouse=True)
def _clean_db():
    reset_mock_db()
    with patch("app.routes.auth.get_collection", side_effect=get_mock_collection):
        yield


@pytest.mark.anyio
async def test_register_success(client):
    resp = await client.post("/auth/register", json={
        "email": "fa@airline.com",
        "password": "securepass",
        "profile": {
            "display_name": "Jane",
            "base_city": "ORD",
            "seniority_number": 500,
            "total_base_fas": 3000,
            "position_min": 1,
            "position_max": 4,
        },
    })
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["email"] == "fa@airline.com"
    assert body["user"]["profile"]["base_city"] == "ORD"


@pytest.mark.anyio
async def test_register_duplicate_email(client):
    payload = {
        "email": "fa@airline.com",
        "password": "securepass",
        "profile": {
            "display_name": "Jane",
            "base_city": "ORD",
            "seniority_number": 500,
            "total_base_fas": 3000,
            "position_min": 1,
            "position_max": 4,
        },
    }
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    resp2 = await client.post("/auth/register", json=payload)
    assert resp2.status_code == 409


@pytest.mark.anyio
async def test_login_success(client):
    await client.post("/auth/register", json={
        "email": "fa@airline.com",
        "password": "securepass",
        "profile": {
            "display_name": "Jane",
            "base_city": "ORD",
            "seniority_number": 500,
            "total_base_fas": 3000,
            "position_min": 1,
            "position_max": 4,
        },
    })
    resp = await client.post("/auth/login", json={
        "email": "fa@airline.com",
        "password": "securepass",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["user"]["email"] == "fa@airline.com"


@pytest.mark.anyio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "fa@airline.com",
        "password": "securepass",
        "profile": {
            "display_name": "Jane",
            "base_city": "ORD",
            "seniority_number": 500,
            "total_base_fas": 3000,
            "position_min": 1,
            "position_max": 4,
        },
    })
    resp = await client.post("/auth/login", json={
        "email": "fa@airline.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_login_nonexistent_user(client):
    resp = await client.post("/auth/login", json={
        "email": "nobody@airline.com",
        "password": "whatever",
    })
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_refresh_token_rotation(client):
    reg = await client.post("/auth/register", json={
        "email": "fa@airline.com",
        "password": "securepass",
        "profile": {
            "display_name": "Jane",
            "base_city": "ORD",
            "seniority_number": 500,
            "total_base_fas": 3000,
            "position_min": 1,
            "position_max": 4,
        },
    })
    refresh = reg.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["email"] == "fa@airline.com"


@pytest.mark.anyio
async def test_refresh_with_access_token_fails(client):
    reg = await client.post("/auth/register", json={
        "email": "fa@airline.com",
        "password": "securepass",
        "profile": {
            "display_name": "Jane",
            "base_city": "ORD",
            "seniority_number": 500,
            "total_base_fas": 3000,
            "position_min": 1,
            "position_max": 4,
        },
    })
    access = reg.json()["access_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_refresh_without_token_fails(client):
    resp = await client.post("/auth/refresh", json={})
    assert resp.status_code == 400
