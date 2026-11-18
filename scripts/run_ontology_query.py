#!/usr/bin/env python3
"""Run a SPARQL query over the RevOps Lakehouse Ontology with full lineage tracing.

Usage:
    # Run the canonical ground-truth RevOps query:
    .venv/bin/python scripts/run_ontology_query.py

    # Compile and regenerate W3C Turtle and OBDA files:
    .venv/bin/python scripts/run_ontology_query.py --compile-ontology
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ontology.engine import default_ontology_engine
from src.ontology.generator import OntologyArtifactGenerator, load_ontology_spec


DEFAULT_QUERY = """
PREFIX : <http://revops.org/ontology#>

SELECT ?account_id ?account_name ?deal_name ?deal_type ?deal_stage ?deal_amount ?wau_drop_pct
WHERE {
    ?account a :EnterpriseAccount ;
             :account_id ?account_id ;
             :name ?account_name ;
             :hasOpportunity ?deal ;
             :hasMetric [
                 a :WAUDropPercentage ;
                 :dropValue ?wau_drop_pct
             ] .
    ?deal a :OpenExpansionDeal ;
          :deal_name ?deal_name ;
          :deal_type ?deal_type ;
          :stage ?deal_stage ;
          :amount ?deal_amount .
    FILTER (?wau_drop_pct >= 30.0)
}
ORDER BY DESC(?wau_drop_pct)
""".strip()


def main():
    parser = argparse.ArgumentParser(description="Query the RevOps Lakehouse Ontology via Virtual SPARQL")
    parser.add_argument("--query", type=str, default=DEFAULT_QUERY, help="SPARQL query string")
    parser.add_argument(
        "--compile-ontology",
        action="store_true",
        help="Recompile YAML to W3C Turtle (.ttl), OBDA (.obda), and R2RML (.r2rml.ttl)",
    )
    args = parser.parse_args()

    if args.compile_ontology:
        print("=" * 70)
        print("Compiling YAML Ontology into W3C & Ontop Artifacts...")
        print("=" * 70)
        spec = load_ontology_spec()
        gen = OntologyArtifactGenerator(spec)
        res = gen.generate_all()
        print(f"[✓] Successfully generated and verified {res['validated_triples']} RDF triples:")
        print(f"  • Turtle (.ttl):  {res['turtle_file']}")
        print(f"  • Ontop (.obda):   {res['obda_file']}")
        print(f"  • R2RML (.r2rml): {res['r2rml_file']}")
        return

    print("=" * 75)
    print("Zero-ETL RevOps Lakehouse Virtual Knowledge Graph Query Runner")
    print("=" * 75)
    print("\n[Input SPARQL Query]:")
    print(args.query)

    result = default_ontology_engine.query_sparql(args.query)

    print("\n" + "-" * 75)
    print(f"[Compiled DuckDB Pushdown SQL] (Execution Time: {result.execution_time_ms} ms):")
    print("-" * 75)
    print(result.compiled_sql)

    print("\n" + "-" * 75)
    print(f"[Query Results] ({len(result.records)} grounded records found):")
    print("-" * 75)
    for i, row in enumerate(result.records, 1):
        print(f"  {i}. {row['account_name']} ({row['account_id']})")
        print(f"     Deal:   {row['deal_name']} [{row['deal_stage']}] - ${float(row['deal_amount']):,.2f}")
        print(f"     Signal: WAU Drop: {row['wau_drop_pct']}% in Q4\n")

    print("-" * 75)
    print("[Semantic Lineage & Graph Trace]:")
    print("-" * 75)
    print(json.dumps(result.lineage, indent=2))
    print("\n[✓] Query execution grounded in Lakehouse Ontology complete.")


if __name__ == "__main__":
    main()

