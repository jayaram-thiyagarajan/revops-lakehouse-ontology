"""Generator that compiles declarative revops_ontology.yaml into

W3C OWL/Turtle (.ttl), Ontop OBDA (.obda), and W3C R2RML (.r2rml.ttl).
"""

from pathlib import Path
from typing import Optional
import yaml
import rdflib
from rdflib import Graph

from src.ontology.models import OntologySpec

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_YAML_PATH = PROJECT_ROOT / "ontology" / "revops_ontology.yaml"
OUTPUT_DIR = PROJECT_ROOT / "ontology"


def load_ontology_spec(yaml_path: Optional[Path] = None) -> OntologySpec:
    """Load and validate the YAML ontology specification."""
    path = yaml_path or DEFAULT_YAML_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return OntologySpec(**data)


class OntologyArtifactGenerator:
    """Generates standard W3C Turtle, Ontop OBDA, and R2RML mapping files."""

    def __init__(self, spec: OntologySpec):
        self.spec = spec
        self.ns = spec.ontology.namespace
        self.prefix = spec.ontology.prefix

    def generate_all(self, output_dir: Optional[Path] = None) -> dict:
        """Generate all 3 ontology artifacts and validate RDF syntax."""
        out_dir = output_dir or OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        ttl_path = out_dir / "revops_ontology.ttl"
        obda_path = out_dir / "mappings.obda"
        r2rml_path = out_dir / "mappings.r2rml.ttl"

        ttl_content = self.generate_owl_turtle()
        with open(ttl_path, "w", encoding="utf-8") as f:
            f.write(ttl_content)

        obda_content = self.generate_ontop_obda()
        with open(obda_path, "w", encoding="utf-8") as f:
            f.write(obda_content)

        r2rml_content = self.generate_r2rml()
        with open(r2rml_path, "w", encoding="utf-8") as f:
            f.write(r2rml_content)

        # Validate Turtle syntax using rdflib
        g = Graph()
        g.parse(ttl_path, format="turtle")
        triple_count = len(g)

        return {
            "turtle_file": ttl_path,
            "obda_file": obda_path,
            "r2rml_file": r2rml_path,
            "validated_triples": triple_count,
        }

    # -----------------------------------------------------------------------
    # 1. W3C OWL / Turtle Generator
    # -----------------------------------------------------------------------
    def generate_owl_turtle(self) -> str:
        lines = [
            f"@prefix : <{self.ns}> .",
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
            f"<{self.ns.rstrip('#')}> a owl:Ontology ;",
            f'    rdfs:label "{self.spec.ontology.name}" ;',
            f'    rdfs:comment "{self.spec.ontology.description}" .',
            "",
            "# ===================================================================",
            "# Classes & Taxonomies",
            "# ===================================================================",
        ]

        # Classes & Subclasses
        for class_name, cdef in self.spec.classes.items():
            lines.append(f":{class_name} a owl:Class ;")
            lines.append(f'    rdfs:label "{class_name}" ;')
            lines.append(f'    rdfs:comment "{cdef.description}" .')
            lines.append("")

            for sub_name, sdef in cdef.subclasses.items():
                lines.append(f":{sub_name} a owl:Class ;")
                lines.append(f"    rdfs:subClassOf :{class_name} ;")
                lines.append(f'    rdfs:label "{sub_name}" ;')
                lines.append(f'    rdfs:comment "{sdef.doc}" .')
                lines.append("")

        lines.append("# ===================================================================")
        lines.append("# Object Properties (Relationships)")
        lines.append("# ===================================================================")

        for rel_name, rdef in self.spec.relationships.items():
            lines.append(f":{rel_name} a owl:ObjectProperty ;")
            lines.append(f"    rdfs:domain :{rdef.source} ;")
            lines.append(f"    rdfs:range :{rdef.target} ;")
            lines.append(f'    rdfs:label "{rel_name}" ;')
            lines.append(f'    rdfs:comment "{rdef.doc}" .')
            lines.append("")

        lines.append("# ===================================================================")
        lines.append("# Datatype Properties")
        lines.append("# ===================================================================")

        type_mapping = {
            "string": "xsd:string",
            "integer": "xsd:integer",
            "decimal": "xsd:decimal",
            "boolean": "xsd:boolean",
            "date": "xsd:date",
            "timestamptz": "xsd:dateTimeStamp",
        }

        for class_name, cdef in self.spec.classes.items():
            for prop_name, pdef in cdef.properties.items():
                xsd_type = type_mapping.get(pdef.type, "xsd:string")
                lines.append(f":{prop_name} a owl:DatatypeProperty ;")
                lines.append(f"    rdfs:domain :{class_name} ;")
                lines.append(f"    rdfs:range {xsd_type} ;")
                lines.append(f'    rdfs:comment "{pdef.doc}" .')
                lines.append("")

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # 2. Ontop Native OBDA Generator
    # -----------------------------------------------------------------------
    def generate_ontop_obda(self) -> str:
        lines = [
            "[PrefixDeclaration]",
            f":\t\t{self.ns}",
            "owl:\t\thttp://www.w3.org/2002/07/owl#",
            "rdf:\t\thttp://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs:\t\thttp://www.w3.org/2000/01/rdf-schema#",
            "xsd:\t\thttp://www.w3.org/2001/XMLSchema#",
            "",
            "[MappingDeclaration] @collection [[",
        ]

        mapping_idx = 1
        # Class Mappings
        for class_name, cdef in self.spec.classes.items():
            pk = cdef.primary_key
            prop_triples = [f":{p} {{{p}}}" for p in cdef.properties if p != pk]
            props_str = " ; ".join(prop_triples)
            props_clause = f" ; {props_str}" if props_str else ""

            # Base class
            lines.extend([
                f"mappingId\tMAPPING-CLASS-{class_name.upper()}",
                f"target\t\t:{class_name.lower()}/{{{pk}}} a :{class_name}{props_clause} .",
                f"source\t\tSELECT * FROM {cdef.table}",
                "",
            ])
            mapping_idx += 1

            # Subclasses with filters
            for sub_name, sdef in cdef.subclasses.items():
                lines.extend([
                    f"mappingId\tMAPPING-SUBCLASS-{sub_name.upper()}",
                    f"target\t\t:{class_name.lower()}/{{{pk}}} a :{sub_name} .",
                    f"source\t\tSELECT * FROM {cdef.table} WHERE {sdef.filter}",
                    "",
                ])
                mapping_idx += 1

        # Relationship Mappings
        for rel_name, rdef in self.spec.relationships.items():
            src_class = self.spec.classes[rdef.source]
            tgt_class = self.spec.classes[rdef.target]
            src_pk = src_class.primary_key
            tgt_pk = tgt_class.primary_key

            join_sql = f"SELECT {src_class.table}.{src_pk}, {tgt_class.table}.{tgt_pk} FROM {src_class.table} JOIN {tgt_class.table} ON {rdef.join}"

            lines.extend([
                f"mappingId\tMAPPING-REL-{rel_name.upper()}",
                f"target\t\t:{rdef.source.lower()}/{{{src_pk}}} :{rel_name} :{rdef.target.lower()}/{{{tgt_pk}}} .",
                f"source\t\t{join_sql}",
                "",
            ])
            mapping_idx += 1

        lines.append("]]")
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # 3. W3C R2RML Generator
    # -----------------------------------------------------------------------
    def generate_r2rml(self) -> str:
        lines = [
            f"@prefix : <{self.ns}> .",
            "@prefix rr: <http://www.w3.org/ns/r2rml#> .",
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
        ]

        for class_name, cdef in self.spec.classes.items():
            pk = cdef.primary_key
            lines.extend([
                f"<#{class_name}Map>",
                f'    rr:logicalTable [ rr:tableName "{cdef.table}" ] ;',
                f'    rr:subjectMap [ rr:template "{self.ns}{class_name.lower()}/{{{pk}}}" ; rr:class :{class_name} ] ;',
            ])

            for p_name in cdef.properties:
                if p_name == pk:
                    continue
                lines.extend([
                    "    rr:predicateObjectMap [",
                    f"        rr:predicate :{p_name} ;",
                    f'        rr:objectMap [ rr:column "{p_name}" ]',
                    "    ] ;",
                ])

            # Terminate statement
            lines[-1] = lines[-1].rstrip(" ;") + " ."
            lines.append("")

        return "\n".join(lines)

