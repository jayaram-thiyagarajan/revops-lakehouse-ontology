#!/usr/bin/env python3
"""Interactive DuckDB query runner for Iceberg Lakehouse tables.

Usage:
    # Run a single query:
    .venv/bin/python scripts/query.py "DESCRIBE accounts;"
    .venv/bin/python scripts/query.py "SHOW TABLES;"

    # Interactive SQL prompt:
    .venv/bin/python scripts/query.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.warehouse.query import default_engine


def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Running: {query}\n")
        default_engine.show(query)
        return

    print("=" * 65)
    print("RevOps Lakehouse - Interactive DuckDB SQL Prompt (Iceberg Views)")
    print("Type your SQL query and press Enter. Type 'exit' or 'quit' to stop.")
    print("=" * 65)
    print("Available tables: accounts, contacts, opportunities, campaigns,")
    print("                  campaign_daily_costs, campaign_touches, product_events\n")

    con = default_engine.get_connection()
    while True:
        try:
            query = input("duckdb> ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "\\q"):
                print("Bye!")
                break
            con.sql(query).show()
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()

