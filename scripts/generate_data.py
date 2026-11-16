#!/usr/bin/env python3
"""CLI script to generate synthetic RevOps GTM data and load it into Iceberg tables."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.generator.gtm_generator import GTMDataGenerator
from src.generator.loader import load_dataset_to_iceberg
from src.warehouse.query import default_engine


def main():
    parser = argparse.ArgumentParser(description="Generate and ingest synthetic RevOps data into Iceberg")
    parser.add_argument("--accounts", type=int, default=30, help="Total number of accounts to generate (default: 30)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible data (default: 42)")
    parser.add_argument(
        "--recreate",
        action="store_true",
        default=True,
        help="Recreate Iceberg tables from scratch before loading (default: True)",
    )
    args = parser.parse_args()

    print("=" * 75)
    print("Generating Coordinated GTM Lakehouse Synthetic Data...")
    print(f"Parameters: accounts={args.accounts}, seed={args.seed}, recreate_tables={args.recreate}")
    print("=" * 75)

    # 1. Generate Dataset
    gen = GTMDataGenerator(seed=args.seed, total_accounts=args.accounts)
    dataset = gen.generate_all()

    # 2. Ingest into Iceberg
    print("\nIngesting PyArrow batches into Apache Iceberg tables...")
    counts = load_dataset_to_iceberg(dataset, overwrite_tables=args.recreate)

    print("\n[✓] Successfully committed snapshots to Iceberg:")
    for table_name, count in counts.items():
        print(f"  • {table_name:22} -> {count:6d} rows committed")

    # 3. Verify in DuckDB
    print("\n" + "-" * 75)
    print("Verifying Ingestion via DuckDB Iceberg Engine:")
    print("-" * 75)
    for table_name in counts:
        c = default_engine.execute(f"SELECT count(*) FROM {table_name};")[0][0]
        print(f"  • {table_name:22} -> DuckDB row count: {c}")

    # 4. Run Ground-Truth Scenario Query
    print("\n" + "=" * 75)
    print("Executing Ground-Truth Test Query:")
    print("Question: Which Enterprise accounts in Q4 saw a >=30% drop in weekly active")
    print("          users while having an open expansion deal?")
    print("=" * 75)

    scenario_sql = """
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
        a.name AS account_name,
        a.tier,
        o.deal_name,
        o.deal_type,
        o.stage AS deal_stage,
        o.amount AS deal_amount,
        round(u.early_q4_wau, 1) AS oct_wau,
        round(u.late_q4_wau, 1) AS dec_wau,
        round((u.early_q4_wau - u.late_q4_wau) * 100.0 / u.early_q4_wau, 1) AS wau_drop_pct
    FROM accounts a
    JOIN opportunities o ON a.account_id = o.account_id
    JOIN usage_trends u ON a.account_id = u.account_id
    WHERE a.tier = 'Enterprise'
      AND o.deal_type = 'Expansion'
      AND o.is_closed = false
      AND (u.early_q4_wau - u.late_q4_wau) * 100.0 / u.early_q4_wau >= 30.0
    ORDER BY wau_drop_pct DESC;
    """

    default_engine.show(scenario_sql)

    print("\n[✓] Synthetic data generation & Iceberg Lakehouse ingestion completed!")


if __name__ == "__main__":
    main()

