"""Unit tests for synthetic GTM data generation and Iceberg ingestion."""

import pytest
from src.generator.gtm_generator import GTMDataGenerator
from src.warehouse.query import default_engine


def test_generator_structure_and_foreign_keys():
    """Verify generated dataset integrity and relational consistency."""
    gen = GTMDataGenerator(seed=123, total_accounts=10)
    dataset = gen.generate_all()

    account_ids = {a["account_id"] for a in dataset.accounts}
    contact_ids = {c["contact_id"] for c in dataset.contacts}
    campaign_ids = {cmp["campaign_id"] for cmp in dataset.campaigns}

    assert len(account_ids) == 10
    assert len(contact_ids) > 0
    assert len(campaign_ids) == 6

    # Verify foreign key consistency
    for contact in dataset.contacts:
        assert contact["account_id"] in account_ids

    for opp in dataset.opportunities:
        assert opp["account_id"] in account_ids

    for touch in dataset.campaign_touches:
        assert touch["contact_id"] in contact_ids
        assert touch["campaign_id"] in campaign_ids

    for cost in dataset.campaign_daily_costs:
        assert cost["campaign_id"] in campaign_ids

    for event in dataset.product_events:
        assert event["account_id"] in account_ids


def test_ground_truth_target_accounts_query():
    """Verify that querying Iceberg through DuckDB returns the exact target accounts."""
    sql = """
    WITH weekly_active_users AS (
        SELECT 
            account_id,
            date_trunc('week', event_time) AS week_start,
            count(DISTINCT user_id) AS wau
        FROM product_events
        WHERE event_time >= '2024-10-01' AND event_time <= '2024-12-31'
        GROUP BY account_id, date_trunc('week', event_time)
    ),
    usage_trends AS (
        SELECT 
            account_id,
            avg(CASE WHEN week_start < '2024-11-01' THEN wau END) AS early_q4_wau,
            avg(CASE WHEN week_start >= '2024-12-01' THEN wau END) AS late_q4_wau
        FROM weekly_active_users
        GROUP BY account_id
    )
    SELECT 
        a.account_id,
        a.name,
        round((u.early_q4_wau - u.late_q4_wau) * 100.0 / u.early_q4_wau, 1) AS wau_drop_pct
    FROM accounts a
    JOIN opportunities o ON a.account_id = o.account_id
    JOIN usage_trends u ON a.account_id = u.account_id
    WHERE a.tier = 'Enterprise'
      AND o.deal_type = 'Expansion'
      AND o.is_closed = false
      AND (u.early_q4_wau - u.late_q4_wau) * 100.0 / u.early_q4_wau >= 30.0
    ORDER BY a.account_id;
    """
    rows = default_engine.execute(sql)
    assert len(rows) == 2

    # Expect Acme Corporation and NovaTech Solutions
    acc_ids = [r[0] for r in rows]
    assert acc_ids == ["acc_ent_001", "acc_ent_002"]

    # Both drops should be > 50%
    assert rows[0][2] >= 50.0
    assert rows[1][2] >= 50.0

