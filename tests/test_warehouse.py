"""Unit tests for Iceberg Lakehouse catalog, schemas, and DuckDB engine."""

import pytest
from src.warehouse.catalog import get_catalog
from src.warehouse.manager import (
    create_gtm_tables,
    get_table,
    inspect_table,
    list_gtm_tables,
)
from src.warehouse.query import DuckDBIcebergEngine
from src.warehouse.schemas import GTM_TABLE_DEFINITIONS


def test_gtm_table_definitions_exist():
    """Verify all 7 core GTM tables are defined."""
    expected_tables = {
        "accounts",
        "contacts",
        "opportunities",
        "campaigns",
        "campaign_daily_costs",
        "campaign_touches",
        "product_events",
    }
    assert set(GTM_TABLE_DEFINITIONS.keys()) == expected_tables


def test_create_and_list_tables():
    """Verify tables can be created and listed from the catalog."""
    tables = create_gtm_tables(overwrite=False)
    assert len(tables) == 7
    assert "accounts" in tables
    assert "campaigns" in tables
    assert "campaign_daily_costs" in tables
    assert "product_events" in tables

    table_names = list_gtm_tables()
    assert "campaigns" in table_names
    assert "campaign_daily_costs" in table_names


def test_partition_specs():
    """Verify partition specs on events, touches, and daily costs."""
    events_table = get_table("product_events")
    assert len(events_table.spec().fields) == 1
    assert events_table.spec().fields[0].name == "event_time_day"

    touches_table = get_table("campaign_touches")
    assert len(touches_table.spec().fields) == 1
    assert touches_table.spec().fields[0].name == "touch_time_month"

    daily_costs_table = get_table("campaign_daily_costs")
    assert len(daily_costs_table.spec().fields) == 1
    assert daily_costs_table.spec().fields[0].name == "date_month"


def test_inspect_table_metadata():
    """Verify table metadata inspection returns snapshot and updated schema info."""
    acc_info = inspect_table("accounts")
    assert acc_info["table_name"] == "accounts"
    assert len(acc_info["schema_fields"]) == 10
    assert any("num_employees" in f for f in acc_info["schema_fields"])

    contact_info = inspect_table("contacts")
    assert len(contact_info["schema_fields"]) == 10
    assert any("status" in f for f in contact_info["schema_fields"])

    touches_info = inspect_table("campaign_touches")
    # Verify campaign_id is present and cost is removed
    assert any("campaign_id" in f for f in touches_info["schema_fields"])
    assert not any("cost" in f for f in touches_info["schema_fields"])


def test_duckdb_iceberg_query():
    """Verify DuckDB can query Iceberg tables."""
    engine = DuckDBIcebergEngine()
    engine.refresh_views()
    rows = engine.execute("SELECT count(*) FROM campaigns;")
    assert rows[0][0] >= 0

    # Test describe on campaign_daily_costs
    desc = engine.describe_table("campaign_daily_costs")
    col_names = [col[0] for col in desc]
    assert "cost_id" in col_names
    assert "campaign_id" in col_names
    assert "date" in col_names
    assert "cost" in col_names
