"""High-level Ontology Query & Lineage Engine for RevOps Lakehouse."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml

from src.ontology.generator import load_ontology_spec
from src.ontology.models import OntologySpec
from src.ontology.sparql_compiler import CompiledQuery, SPARQLToDuckDBCompiler
from src.warehouse.query import DuckDBIcebergEngine, default_engine


@dataclass
class OntologyQueryResult:
    records: List[Dict[str, Any]]
    compiled_sql: str
    projected_variables: List[str]
    lineage: Dict[str, Any]
    execution_time_ms: float


class OntologyEngine:
    """Provides high-level semantic query execution, lineage tracing,

    and context generation for AI agents over the Iceberg Lakehouse.
    """

    def __init__(
        self,
        spec: Optional[OntologySpec] = None,
        warehouse_engine: Optional[DuckDBIcebergEngine] = None,
    ):
        self.spec = spec or load_ontology_spec()
        self.compiler = SPARQLToDuckDBCompiler(self.spec)
        self.warehouse = warehouse_engine or default_engine

    def query_sparql(self, sparql_query: str) -> OntologyQueryResult:
        """Compile a SPARQL query, execute pushdown SQL on Iceberg, and return grounded results with lineage.

        Args:
            sparql_query: SPARQL SELECT query.

        Returns:
            OntologyQueryResult containing records, compiled SQL, and lineage.
        """
        start_time = time.perf_counter()

        # 1. Compile SPARQL to DuckDB Pushdown SQL
        compiled: CompiledQuery = self.compiler.compile(sparql_query)

        # 2. Execute SQL against DuckDB views over Iceberg Parquet files
        con = self.warehouse.get_connection()
        arrow_result = con.sql(compiled.sql).to_arrow_table()
        records = arrow_result.to_pylist()

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 3. Construct Semantic Lineage
        lineage = {
            "involved_classes": list(compiled.involved_classes),
            "involved_relationships": list(compiled.involved_relationships),
            "involved_metrics": list(compiled.involved_metrics),
            "pushdown_tables": [
                self.spec.classes[c].table
                for c in compiled.involved_classes
                if c in self.spec.classes
            ],
            "execution_engine": "DuckDB (Iceberg Extension, Zero-ETL)",
        }

        return OntologyQueryResult(
            records=records,
            compiled_sql=compiled.sql,
            projected_variables=compiled.projected_variables,
            lineage=lineage,
            execution_time_ms=duration_ms,
        )

    def get_prompt_context(self) -> str:
        """Export a compact semantic context formatted for AI Agent system prompts."""
        lines = [
            "# ==================================================================",
            "# RevOps Knowledge Graph & Semantic Metric Ontology",
            "# ==================================================================",
            "You have access to a Zero-ETL Lakehouse Virtual Knowledge Graph.",
            "Use the classes, relationships, and metrics below to formulate deterministic queries.",
            "",
            "## 1. Concepts & Classes",
        ]

        for c_name, cdef in self.spec.classes.items():
            lines.append(f"- **{c_name}**: {cdef.description} (Table: `{cdef.table}`)")
            if cdef.subclasses:
                sub_desc = ", ".join([f"`{s}` ({sdef.doc})" for s, sdef in cdef.subclasses.items()])
                lines.append(f"  - Subclasses: {sub_desc}")

        lines.append("\n## 2. Valid Semantic Relationships (Edges)")
        for r_name, rdef in self.spec.relationships.items():
            lines.append(f"- `:{r_name}`: `{rdef.source}` -> `{rdef.target}` ({rdef.doc})")

        lines.append("\n## 3. Semantic Metric Contracts")
        for m_name, mdef in self.spec.metrics.items():
            formula_str = f" Formula: `{mdef.formula}`" if mdef.formula else ""
            lines.append(f"- **{mdef.name}** (on `{mdef.source_concept}`): {mdef.description}{formula_str}")

        return "\n".join(lines)

    def get_concept_details(self, concept_name: str) -> Dict[str, Any]:
        """Return attributes, relationships, and metadata for a specific concept."""
        if concept_name in self.spec.classes:
            cdef = self.spec.classes[concept_name]
            return {
                "concept": concept_name,
                "table": cdef.table,
                "description": cdef.description,
                "properties": {p: pdef.doc for p, pdef in cdef.properties.items()},
                "subclasses": {s: sdef.doc for s, sdef in cdef.subclasses.items()},
                "outbound_relationships": {
                    r_name: rdef.target
                    for r_name, rdef in self.spec.relationships.items()
                    if rdef.source == concept_name
                },
                "inbound_relationships": {
                    r_name: rdef.source
                    for r_name, rdef in self.spec.relationships.items()
                    if rdef.target == concept_name
                },
            }
        return {}


# Default singleton instance
default_ontology_engine = OntologyEngine()
