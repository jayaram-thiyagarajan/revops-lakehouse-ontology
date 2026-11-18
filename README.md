# Zero-ETL GTM Lakehouse Ontology

A RevOps Lakehouse architecture bridging **Apache Iceberg**, **DuckDB**, and a **Virtual Knowledge Graph / Semantic Layer** to provide deterministic, hallucination-free answers for AI agents over cross-silo GTM data.

---

## Architecture Overview

```
                  ┌─────────────────────────────────────────┐
                  │          AI RevOps Agent & UI           │
                  │   (LangGraph/DSPy + React Chat UI)      │
                  └────────────────────┬────────────────────┘
                                       │ SPARQL / SQL
                  ┌────────────────────▼────────────────────┐
                  │    Virtual Knowledge Graph / Semantic   │
                  │  (Ontop / PuppyGraph / Schema Ontology) │
                  └────────────────────┬────────────────────┘
                                       │ Pushdown SQL Scans
                  ┌────────────────────▼────────────────────┐
                  │         DuckDB Analytical Engine        │
                  │       (Native `iceberg` extension)      │
                  └────────────────────┬────────────────────┘
                                       │ Direct Metadata & Parquet Read
                  ┌────────────────────▼────────────────────┐
                  │       Apache Iceberg Lakehouse          │
                  │  - Catalog: PyIceberg SqlCatalog        │
                  │  - Metadata: Iceberg v2 JSON & Manifests│
                  │  - Storage: Partitioned Parquet         │
                  └─────────────────────────────────────────┘
```

---

## Canonical GTM Tables

The 7 core GTM tables are defined in [`src/warehouse/schemas.py`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/src/warehouse/schemas.py):

| Table Name | Description | Key Partition Transform |
| :--- | :--- | :--- |
| `gtm.accounts` | Customer & prospect accounts, tier, ARR, health score, employees | Unpartitioned |
| `gtm.contacts` | Buyer personas, roles, lifecycle status, mapped to accounts | Unpartitioned |
| `gtm.opportunities` | CRM pipeline deals, stages, amounts, close dates | Unpartitioned |
| `gtm.campaigns` | Marketing campaigns across channels, budget, and dates | Unpartitioned |
| `gtm.campaign_daily_costs` | Daily spend, impressions, and clicks per campaign | `MonthTransform(date)` |
| `gtm.campaign_touches` | Contact-level touchpoints referencing `campaign_id` | `MonthTransform(touch_time)` |
| `gtm.product_events` | Granular telemetry (logins, reports, feature usage) | `DayTransform(event_time)` |

---

## Quickstart

### 1. Run the Warehouse Initializer & Data Generator
```bash
# Initialize empty tables
.venv/bin/python scripts/init_warehouse.py

# Generate realistic synthetic GTM data and commit snapshots to Iceberg
.venv/bin/python scripts/generate_data.py
```

### 2. Run the Unit Tests
```bash
.venv/bin/pytest -v
```

### 3. Query the Virtual Ontology Layer (SPARQL -> DuckDB Pushdown)
```bash
# Run the canonical ground-truth RevOps SPARQL query with lineage tracing
.venv/bin/python scripts/run_ontology_query.py

# Recompile the YAML ontology into formal W3C Turtle (.ttl), Ontop (.obda), and R2RML (.r2rml.ttl)
.venv/bin/python scripts/run_ontology_query.py --compile-ontology
```

---

## Virtual Ontology Structure

The ontology is defined declaratively in [`ontology/revops_ontology.yaml`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/ontology/revops_ontology.yaml) and automatically compiled into standard W3C semantic artifacts:

* [`ontology/revops_ontology.yaml`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/ontology/revops_ontology.yaml): Human-friendly declarative YAML defining classes, relationships, and metric formulas.
* [`ontology/revops_ontology.ttl`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/ontology/revops_ontology.ttl): W3C OWL/Turtle ontology (289 verified RDF triples).
* [`ontology/mappings.obda`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/ontology/mappings.obda): Ontop native OBDA mapping file for virtual graph pushdown.
* [`ontology/mappings.r2rml.ttl`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/ontology/mappings.r2rml.ttl): W3C R2RML mapping specification.
* [`src/ontology/sparql_compiler.py`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/src/ontology/sparql_compiler.py): Translates SPARQL queries directly into optimized DuckDB SQL over Iceberg tables.
* [`src/ontology/engine.py`](file:///Users/jayaramthiyagarajan/code/revops-lakehouse-ontology/src/ontology/engine.py): High-level interface providing agent prompt context, query execution, and semantic lineage.

---

## Querying DuckDB Directly
```bash
# Interactive DuckDB prompt over Iceberg views
.venv/bin/python scripts/query.py

# Or run one-liner queries
.venv/bin/python scripts/query.py "SELECT count(*) FROM product_events;"
```

```python
from src.warehouse.query import default_engine

# Run queries directly over the registered Iceberg views
df = default_engine.query_df("SELECT * FROM accounts;")
print(df)
```

