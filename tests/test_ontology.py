"""Unit tests for RevOps Ontology layer, SPARQL compilation, and lineage."""

import pytest
from src.ontology.engine import default_ontology_engine
from src.ontology.generator import OntologyArtifactGenerator, load_ontology_spec
from src.ontology.sparql_compiler import SPARQLToDuckDBCompiler


def test_ontology_spec_loading():
    """Verify that the declarative YAML ontology loads with all expected classes and relations."""
    spec = load_ontology_spec()
    assert spec.ontology.name == "RevOpsGTMOntology"
    assert "Account" in spec.classes
    assert "Opportunity" in spec.classes
    assert "Campaign" in spec.classes
    assert "hasOpportunity" in spec.relationships
    assert "hasTelemetryEvent" in spec.relationships
    assert "wau_drop_percentage" in spec.metrics


def test_ontology_artifact_generation(tmp_path):
    """Verify compilation of YAML into W3C Turtle, Ontop OBDA, and R2RML."""
    spec = load_ontology_spec()
    gen = OntologyArtifactGenerator(spec)
    result = gen.generate_all(output_dir=tmp_path)

    assert result["validated_triples"] > 100
    assert result["turtle_file"].exists()
    assert result["obda_file"].exists()
    assert result["r2rml_file"].exists()

    # Read OBDA content to verify mappings
    obda_text = result["obda_file"].read_text()
    assert "MAPPING-CLASS-ACCOUNT" in obda_text
    assert "MAPPING-SUBCLASS-ENTERPRISEACCOUNT" in obda_text
    assert "MAPPING-REL-HASOPPORTUNITY" in obda_text


def test_sparql_compilation_and_lineage():
    """Verify that a SPARQL query compiles to deterministic DuckDB SQL with semantic lineage."""
    sparql = """
    PREFIX : <http://revops.org/ontology#>
    SELECT ?account_id ?account_name ?deal_name ?wau_drop_pct
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
              :deal_name ?deal_name .
        FILTER (?wau_drop_pct >= 30.0)
    }
    """
    compiler = SPARQLToDuckDBCompiler()
    compiled = compiler.compile(sparql)

    # Check SQL pushdown constructs
    assert "weekly_active_users AS (" in compiled.sql
    assert "usage_trends AS (" in compiled.sql
    assert "JOIN opportunities ON" in compiled.sql
    assert "accounts.tier = 'Enterprise'" in compiled.sql
    assert "opportunities.deal_type = 'Expansion'" in compiled.sql
    assert "is_closed = false" in compiled.sql

    # Check lineage
    assert "Account" in compiled.involved_classes
    assert "Opportunity" in compiled.involved_classes
    assert "hasOpportunity" in compiled.involved_relationships
    assert "WAUDropPercentage" in compiled.involved_metrics


def test_end_to_end_ontology_query_execution():
    """Verify end-to-end SPARQL execution over Iceberg tables via DuckDB."""
    sparql = """
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
    """
    res = default_ontology_engine.query_sparql(sparql)

    assert len(res.records) == 2
    acc_ids = [r["account_id"] for r in res.records]
    assert "acc_ent_001" in acc_ids
    assert "acc_ent_002" in acc_ids

    # Lineage verification
    assert res.lineage["execution_engine"] == "DuckDB (Iceberg Extension, Zero-ETL)"
    assert "accounts" in res.lineage["pushdown_tables"]
    assert "opportunities" in res.lineage["pushdown_tables"]


def test_agent_prompt_context_export():
    """Verify that the engine exports a clean semantic context for AI agents."""
    context = default_ontology_engine.get_prompt_context()
    assert "RevOps Knowledge Graph & Semantic Metric Ontology" in context
    assert "EnterpriseAccount" in context
    assert ":hasOpportunity" in context
    assert "WAUDropPercentage" in context

