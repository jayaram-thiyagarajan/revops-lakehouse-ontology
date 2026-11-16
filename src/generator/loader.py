"""Ingestion loader that commits PyArrow datasets to Apache Iceberg tables."""

from typing import Dict, List, Optional
import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.io.pyarrow import schema_to_pyarrow
from pyiceberg.table import Table

from src.generator.gtm_generator import GTMDataset
from src.warehouse.catalog import get_catalog
from src.warehouse.config import LakehouseConfig, default_config
from src.warehouse.manager import create_gtm_tables, get_table
from src.warehouse.query import default_engine
from src.warehouse.schemas import GTM_TABLE_DEFINITIONS


def convert_records_to_arrow(records: List[dict], table: Table) -> pa.Table:
    """Convert a list of Python dicts into a PyArrow Table matching the Iceberg table schema.

    Args:
        records: List of dictionaries representing table rows.
        table: PyIceberg Table instance.

    Returns:
        PyArrow Table strictly typed to the Iceberg schema specification.
    """
    arrow_schema = schema_to_pyarrow(table.schema())
    pydict = {col.name: [row.get(col.name) for row in records] for col in arrow_schema}
    return pa.Table.from_pydict(pydict, schema=arrow_schema)


def load_dataset_to_iceberg(
    dataset: GTMDataset,
    overwrite_tables: bool = True,
    config: Optional[LakehouseConfig] = None,
) -> Dict[str, int]:
    """Load a GTMDataset into Apache Iceberg tables and refresh DuckDB views.

    Args:
        dataset: GTMDataset instance containing rows for all tables.
        overwrite_tables: If True, recreates empty tables before ingestion.
        config: Optional LakehouseConfig.

    Returns:
        Dictionary mapping table name to row count inserted.
    """
    cfg = config or default_config
    if overwrite_tables:
        create_gtm_tables(overwrite=True, config=cfg)

    table_data_map = {
        "accounts": dataset.accounts,
        "contacts": dataset.contacts,
        "opportunities": dataset.opportunities,
        "campaigns": dataset.campaigns,
        "campaign_daily_costs": dataset.campaign_daily_costs,
        "campaign_touches": dataset.campaign_touches,
        "product_events": dataset.product_events,
    }

    row_counts = {}

    for table_name, records in table_data_map.items():
        table = get_table(table_name, config=cfg)
        arrow_table = convert_records_to_arrow(records, table)
        table.append(arrow_table)
        row_counts[table_name] = len(records)

    # Refresh DuckDB views so newly committed snapshots are immediately queryable
    default_engine.refresh_views()

    return row_counts

