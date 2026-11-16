#!/usr/bin/env python3
"""Initialize the Iceberg Lakehouse catalog and inspect canonical GTM tables."""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.warehouse.catalog import get_catalog
from src.warehouse.manager import create_gtm_tables, inspect_table
from src.warehouse.query import DuckDBIcebergEngine


def main():
    parser = argparse.ArgumentParser(description="Initialize RevOps Iceberg Tables")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite and recreate existing tables if schema changed",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Initializing RevOps Apache Iceberg Lakehouse...")
    print(f"Mode: {'Recreating (overwrite)' if args.overwrite else 'Safe create (keep existing)'}")
    print("=" * 70)

    # 1. Initialize catalog & create tables
    tables = create_gtm_tables(overwrite=args.overwrite)
    print(f"\n[✓] Successfully verified/created {len(tables)} Iceberg tables:")
    for name in tables:
        print(f"  • gtm.{name}")

    # 2. Inspect an example table (metadata & partitioning)
    print("\n" + "-" * 70)
    print("Inspecting Iceberg Metadata: gtm.campaign_daily_costs")
    print("-" * 70)
    info = inspect_table("campaign_daily_costs")
    print(f"Metadata file: {info['metadata_location']}")
    print(f"Format version: {info['format_version']}")
    print(f"Partition fields: {info['partition_fields']}")
    print("Schema fields:")
    for f in info["schema_fields"]:
        print(f"  - {f}")

    # 3. DuckDB Iceberg Engine Verification
    print("\n" + "-" * 70)
    print("Testing DuckDB Iceberg Extension Query Engine")
    print("-" * 70)
    engine = DuckDBIcebergEngine()
    engine.refresh_views()
    for table_name in tables:
        count = engine.execute(f"SELECT count(*) FROM {table_name};")[0][0]
        print(f"  • {table_name:22} -> row count: {count}")

    print("\n[✓] Lakehouse storage & query engine setup is complete and ready.")


if __name__ == "__main__":
    main()
