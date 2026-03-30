"""Tests for airline configuration system."""
from app.services.airline_configs import (
    AirlineConfig,
    DEFAULT_CONFIG,
    get_airline_config,
    list_airline_configs,
    register_airline_config,
    AIRLINE_CONFIGS,
)
from app.services.pdf_parser import parse_bid_sheet_text
import re


def test_default_config_exists():
    config = get_airline_config()
    assert config.airline_code == "default"
    assert config.deadhead_suffix == "D"
    assert config.redeye_depart_after == 21
    assert config.redeye_arrive_before == 6


def test_get_unknown_airline_falls_back_to_default():
    config = get_airline_config("nonexistent_airline")
    assert config is DEFAULT_CONFIG


def test_get_airline_config_none_returns_default():
    config = get_airline_config(None)
    assert config is DEFAULT_CONFIG


def test_list_airline_configs():
    configs = list_airline_configs()
    assert len(configs) >= 1
    assert any(c["code"] == "default" for c in configs)
    for c in configs:
        assert "code" in c
        assert "description" in c


def test_register_airline_config():
    test_config = AirlineConfig(
        airline_code="test_airline",
        description="Test airline format",
        footer_re=DEFAULT_CONFIG.footer_re,
        seq_re=DEFAULT_CONFIG.seq_re,
        rpt_re=DEFAULT_CONFIG.rpt_re,
        rls_re=DEFAULT_CONFIG.rls_re,
        ttl_re=DEFAULT_CONFIG.ttl_re,
        leg_prefix_re=DEFAULT_CONFIG.leg_prefix_re,
        layover_hotel_re=DEFAULT_CONFIG.layover_hotel_re,
        layover_transport_re=DEFAULT_CONFIG.layover_transport_re,
        category_line_re=DEFAULT_CONFIG.category_line_re,
        dash_re=DEFAULT_CONFIG.dash_re,
        redeye_depart_after=22,
        redeye_arrive_before=5,
    )
    register_airline_config(test_config)

    retrieved = get_airline_config("test_airline")
    assert retrieved.airline_code == "test_airline"
    assert retrieved.redeye_depart_after == 22
    assert retrieved.redeye_arrive_before == 5

    # Clean up
    del AIRLINE_CONFIGS["test_airline"]


def test_parse_bid_sheet_text_with_airline_code():
    """Parsing with explicit airline_code='default' should produce same results as None."""
    sample = (
        "F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD 777 INTL PAGE 1\n"
        "SEQ 100 2 OPS POSN 1 THRU 9 5 10 15\n"
        "RPT 0600/0600 5 10 15\n"
        "1 1/2 777 1234 ORD 0700/0700 NRT 1500/1500 8.00 5 10 15\n"
        "RLS 1600/1600 1.00 9.00 10.00 5 10 15\n"
        "TTL 8.00 1.00 9.00 34.00\n"
        "-----------------------------------------------------------\n"
    )
    result_default = parse_bid_sheet_text(sample, airline_code=None)
    result_explicit = parse_bid_sheet_text(sample, airline_code="default")

    assert result_default["total_sequences"] == result_explicit["total_sequences"]
    assert result_default["sequences"][0]["seq_number"] == result_explicit["sequences"][0]["seq_number"]


def test_airlines_endpoint():
    """Test the /airlines endpoint."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/airlines")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) >= 1
    assert data["data"][0]["code"] == "default"
