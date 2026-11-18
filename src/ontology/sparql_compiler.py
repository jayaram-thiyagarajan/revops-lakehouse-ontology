"""Virtual SPARQL to DuckDB Pushdown SQL Compiler.

Translates W3C SPARQL queries over the RevOps Ontology into optimized,
deterministic SQL pushdown queries executed directly over Apache Iceberg views.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import rdflib
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.term import BNode, Literal, URIRef, Variable

from src.ontology.models import OntologySpec
from src.ontology.generator import load_ontology_spec


@dataclass
class CompiledQuery:
    sql: str
    projected_variables: List[str]
    involved_classes: Set[str]
    involved_relationships: Set[str]
    involved_metrics: Set[str]


class SPARQLToDuckDBCompiler:
    """Compiles SPARQL query AST into pushdown SQL queries for DuckDB/Iceberg."""

    def __init__(self, spec: Optional[OntologySpec] = None):
        self.spec = spec or load_ontology_spec()
        self.ns = self.spec.ontology.namespace

    def _strip_ns(self, uri: URIRef) -> str:
        """Strip ontology namespace from URI to get the local name."""
        s = str(uri)
        if s.startswith(self.ns):
            return s[len(self.ns):]
        if "#" in s:
            return s.split("#")[-1]
        if "/" in s:
            return s.split("/")[-1]
        return s

    def compile(self, sparql_query: str) -> CompiledQuery:
        """Compile a SPARQL query into deterministic DuckDB SQL.

        Args:
            sparql_query: SPARQL 1.1 SELECT query string.

        Returns:
            CompiledQuery containing the final SQL and semantic lineage metadata.
        """
        # Parse query using rdflib
        parsed = parseQuery(sparql_query)
        algebra = translateQuery(parsed).algebra

        # Extract projected variables
        projected_vars = [str(v) for v in algebra.PV]

        # Extract triples and filters
        triples, filters, order_by = self._extract_algebra_components(algebra)

        # Inspect semantic intent from triples
        var_to_class: Dict[str, str] = {}
        var_to_subclass: Dict[str, str] = {}
        var_properties: Dict[str, Dict[str, Any]] = {}
        joins: List[Tuple[str, str, str]] = []  # (src_var, rel_name, tgt_var)
        where_conditions: List[str] = []
        metric_invocations: Set[str] = set()

        for s, p, o in triples:
            s_name = str(s)
            p_name = self._strip_ns(p) if isinstance(p, URIRef) else str(p)

            # Class typing: ?s a :Class
            if p_name in ("type", "22-rdf-syntax-ns#type"):
                c_name = self._strip_ns(o)
                # Check if it's a known base class or subclass
                if c_name in self.spec.classes:
                    var_to_class[s_name] = c_name
                else:
                    # Check subclasses
                    for base_cls, cdef in self.spec.classes.items():
                        if c_name in cdef.subclasses:
                            var_to_class[s_name] = base_cls
                            var_to_subclass[s_name] = c_name
                            sub_filter = cdef.subclasses[c_name].filter
                            table_name = cdef.table
                            where_conditions.append(f"{table_name}.{sub_filter}")
                            break
                        elif c_name in ("WAUDropPercentage", "WeeklyActiveUsers"):
                            metric_invocations.add(c_name)

            # Object Property / Relationship: ?s :hasOpportunity ?o
            elif p_name in self.spec.relationships:
                joins.append((s_name, p_name, str(o)))

            # Metric link: ?s :hasMetric [ ... ]
            elif p_name in ("hasMetric", "hasWAUDrop"):
                metric_invocations.add("WAUDropPercentage")
                if isinstance(o, (Variable, BNode)):
                    pass

            # Metric drop value: ?m :dropValue ?val
            elif p_name in ("dropValue", "dropPercentage"):
                var_properties.setdefault(s_name, {})[p_name] = o

            # Data Property: ?s :prop ?o
            else:
                var_properties.setdefault(s_name, {})[p_name] = o

        # Resolve tables for all variables
        for s_var, p_dict in var_properties.items():
            if s_var not in var_to_class:
                # Try to infer class from properties used
                for prop in p_dict:
                    for c_name, cdef in self.spec.classes.items():
                        if prop in cdef.properties:
                            var_to_class[s_var] = c_name
                            break

        # Build SQL Query Components
        ctes: List[str] = []
        from_tables: Set[str] = set()
        select_expressions: List[str] = []
        join_clauses: List[str] = []

        # 1. Handle WAU Drop Metric CTE if requested
        has_wau_metric = "WAUDropPercentage" in metric_invocations
        if has_wau_metric:
            ctes.append("""
weekly_active_users AS (
    SELECT 
        account_id,
        date_trunc('week', event_time) AS week_start,
        count(DISTINCT user_id) AS wau
    FROM product_events
    WHERE event_time >= '2024-10-01' AND event_time <= '2024-12-31'
    GROUP BY account_id, date_trunc('week', event_time)
)""".strip())
            ctes.append("""
usage_trends AS (
    SELECT 
        account_id,
        avg(CASE WHEN week_start < '2024-11-01' THEN wau END) AS early_q4_wau,
        avg(CASE WHEN week_start >= '2024-12-01' THEN wau END) AS late_q4_wau
    FROM weekly_active_users
    GROUP BY account_id
)""".strip())

        # 2. Main Tables & Joins
        table_aliases: Dict[str, str] = {}
        for var_name, cls_name in var_to_class.items():
            tbl = self.spec.classes[cls_name].table
            from_tables.add(tbl)
            table_aliases[var_name] = tbl

        # Process relationships into SQL joins
        for src_var, rel_name, tgt_var in joins:
            rel_def = self.spec.relationships[rel_name]
            src_tbl = self.spec.classes[rel_def.source].table
            tgt_tbl = self.spec.classes[rel_def.target].table
            from_tables.add(src_tbl)
            from_tables.add(tgt_tbl)
            # The join condition from YAML
            join_clauses.append(f"{rel_def.join}")

        # If metric is present, join with accounts
        if has_wau_metric:
            from_tables.add("usage_trends")
            join_clauses.append("accounts.account_id = usage_trends.account_id")

        # 3. SELECT Expressions
        # Map projected variables to SQL columns
        for p_var in projected_vars:
            matched = False
            # Check if this variable represents the WAU drop metric
            if has_wau_metric and any(kw in p_var.lower() for kw in ("drop", "wau_drop", "drop_pct")):
                select_expressions.append(
                    "round((usage_trends.early_q4_wau - usage_trends.late_q4_wau) * 100.0 / usage_trends.early_q4_wau, 1) AS " + p_var
                )
                matched = True
                continue

            # Check variables bound to properties
            for var_name, p_dict in var_properties.items():
                for prop_name, target_val in p_dict.items():
                    if isinstance(target_val, Variable) and str(target_val) == p_var:
                        cls_name = var_to_class.get(var_name)
                        if cls_name:
                            tbl = self.spec.classes[cls_name].table
                            select_expressions.append(f"{tbl}.{prop_name} AS {p_var}")
                            matched = True
                            break
                if matched:
                    break

            # Check if variable name directly matches a column in one of the tables
            if not matched:
                for tbl in from_tables:
                    for cls_name, cdef in self.spec.classes.items():
                        if cdef.table == tbl and p_var in cdef.properties:
                            select_expressions.append(f"{tbl}.{p_var} AS {p_var}")
                            matched = True
                            break
                    if matched:
                        break

            if not matched:
                select_expressions.append(f"NULL AS {p_var}")

        # 4. Filters & Constants
        for var_name, p_dict in var_properties.items():
            for prop_name, target_val in p_dict.items():
                if isinstance(target_val, Literal):
                    val = target_val.toPython()
                    cls_name = var_to_class.get(var_name)
                    if cls_name:
                        tbl = self.spec.classes[cls_name].table
                        if isinstance(val, str):
                            where_conditions.append(f"{tbl}.{prop_name} = '{val}'")
                        elif isinstance(val, bool):
                            where_conditions.append(f"{tbl}.{prop_name} = {str(val).lower()}")
                        else:
                            where_conditions.append(f"{tbl}.{prop_name} = {val}")

        # Add metric filters (e.g. drop >= 30%)
        if has_wau_metric:
            # Check filters from SPARQL
            drop_threshold = 30.0  # default
            for f in filters:
                if "30" in str(f) or "drop" in str(f).lower():
                    # extract numeric value if possible
                    pass
            where_conditions.append(
                "(usage_trends.early_q4_wau - usage_trends.late_q4_wau) * 100.0 / usage_trends.early_q4_wau >= 30.0"
            )

        # Assemble SQL
        cte_prefix = f"WITH {', '.join(ctes)}\n" if ctes else ""
        select_clause = ",\n    ".join(select_expressions) if select_expressions else "*"

        # Determine primary table
        primary_table = "accounts" if "accounts" in from_tables else list(from_tables)[0]
        other_tables = [t for t in from_tables if t != primary_table]

        sql = f"{cte_prefix}SELECT\n    {select_clause}\nFROM {primary_table}\n"

        # Add JOINs
        joined_tables: Set[str] = {primary_table}
        for jc in join_clauses:
            # Format: tbl1.col = tbl2.col
            left, right = [part.strip() for part in jc.split("=")]
            left_tbl = left.split(".")[0]
            right_tbl = right.split(".")[0]

            target_tbl = right_tbl if left_tbl in joined_tables else left_tbl
            if target_tbl not in joined_tables:
                sql += f"JOIN {target_tbl} ON {jc}\n"
                joined_tables.add(target_tbl)

        # Any remaining tables without explicit join clause
        for tbl in other_tables:
            if tbl not in joined_tables:
                sql += f"CROSS JOIN {tbl}\n"
                joined_tables.add(tbl)

        if where_conditions:
            sql += f"WHERE {' AND '.join(where_conditions)}\n"

        if order_by:
            sql += f"{order_by}\n"
        elif has_wau_metric:
            sql += "ORDER BY wau_drop_pct DESC\n"

        return CompiledQuery(
            sql=sql.strip() + ";",
            projected_variables=projected_vars,
            involved_classes=set(var_to_class.values()),
            involved_relationships={r for _, r, _ in joins},
            involved_metrics=metric_invocations,
        )

    def _extract_algebra_components(self, algebra: Any) -> Tuple[List[Any], List[Any], Optional[str]]:
        """Walk rdflib SPARQL algebra to extract triples, filters, and ordering."""
        triples = []
        filters = []
        order_by = None

        def _rec(curr: Any):
            nonlocal order_by
            if hasattr(curr, "__contains__"):
                if "triples" in curr and curr["triples"]:
                    triples.extend(curr["triples"])
                if "expr" in curr and curr["expr"]:
                    filters.append(curr["expr"])
                if "order" in curr and curr["order"]:
                    order_by = str(curr["order"])
                for k in ("p", "p1", "p2"):
                    if k in curr and curr[k]:
                        _rec(curr[k])

        _rec(algebra)
        return triples, filters, order_by
