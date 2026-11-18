"""Generator that compiles declarative revops_ontology.yaml into

W3C OWL/Turtle (.ttl), Ontop OBDA (.obda), and W3C R2RML (.r2rml.ttl)
using rdflib's native Graph model and W3C Turtle serializers.
Handles arbitrary additions/edits to classes, properties, subclasses, and relationships.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Optional
import yaml
import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from src.ontology.models import OntologySpec
DEFAULT_YAML_PATH = PROJECT_ROOT / "ontology" / "revops_ontology.yaml"
OUTPUT_DIR = PROJECT_ROOT / "ontology"

RR = Namespace("http://www.w3.org/ns/r2rml#")


def load_ontology_spec(yaml_path: Optional[Path] = None) -> OntologySpec:
    """Load and validate the YAML ontology specification."""
    path = yaml_path or DEFAULT_YAML_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return OntologySpec(**data)


class OntologyArtifactGenerator:
    """Generates standard W3C Turtle, Ontop OBDA, and R2RML mapping files using rdflib."""

    def __init__(self, spec: OntologySpec):
        self.spec = spec
        self.ns = spec.ontology.namespace
        self.prefix = spec.ontology.prefix
        self.REV = Namespace(self.ns)

    def generate_all(self, output_dir: Optional[Path] = None) -> dict:
        """Generate all 3 ontology artifacts and validate RDF syntax."""
        out_dir = output_dir or OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        ttl_path = out_dir / "revops_ontology.ttl"
        obda_path = out_dir / "mappings.obda"
        r2rml_path = out_dir / "mappings.r2rml.ttl"

        # 1. Generate OWL/Turtle using native rdflib Graph
        ttl_content = self.generate_owl_turtle()
        with open(ttl_path, "w", encoding="utf-8") as f:
            f.write(ttl_content)

        # 2. Generate Ontop OBDA (proprietary Ontop mapping format)
        obda_content = self.generate_ontop_obda()
        with open(obda_path, "w", encoding="utf-8") as f:
            f.write(obda_content)

        # 3. Generate W3C R2RML using native rdflib Graph
        r2rml_content = self.generate_r2rml()
        with open(r2rml_path, "w", encoding="utf-8") as f:
            f.write(r2rml_content)

        # Validate Turtle syntax using rdflib
        g = Graph()
        g.parse(ttl_path, format="turtle")
        triple_count = len(g)

        rg = Graph()
        rg.parse(r2rml_path, format="turtle")
        r2rml_triple_count = len(rg)

        return {
            "turtle_file": ttl_path,
            "obda_file": obda_path,
            "r2rml_file": r2rml_path,
            "validated_triples": triple_count,
            "r2rml_triples": r2rml_triple_count,
        }

    # -----------------------------------------------------------------------
    # 1. W3C OWL / Turtle Generator (via rdflib.Graph)
    # -----------------------------------------------------------------------
    def generate_owl_turtle(self) -> str:
        """Construct the formal OWL/RDF ontology using native rdflib Graph primitives."""
        g = Graph()
        g.bind(self.prefix, self.REV)
        g.bind("owl", OWL)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)

        # Ontology metadata
        onto_uri = URIRef(self.ns.rstrip("#"))
        g.add((onto_uri, RDF.type, OWL.Ontology))
        g.add((onto_uri, RDFS.label, Literal(self.spec.ontology.name)))
        g.add((onto_uri, RDFS.comment, Literal(self.spec.ontology.description)))

        # Classes and Subclasses
        for class_name, cdef in self.spec.classes.items():
            cls_uri = self.REV[class_name]
            g.add((cls_uri, RDF.type, OWL.Class))
            g.add((cls_uri, RDFS.label, Literal(class_name)))
            g.add((cls_uri, RDFS.comment, Literal(cdef.description)))

            for sub_name, sdef in cdef.subclasses.items():
                sub_uri = self.REV[sub_name]
                g.add((sub_uri, RDF.type, OWL.Class))
                g.add((sub_uri, RDFS.subClassOf, cls_uri))
                g.add((sub_uri, RDFS.label, Literal(sub_name)))
                g.add((sub_uri, RDFS.comment, Literal(sdef.doc)))

        # Object Properties (Relationships)
        for rel_name, rdef in self.spec.relationships.items():
            rel_uri = self.REV[rel_name]
            g.add((rel_uri, RDF.type, OWL.ObjectProperty))
            if rdef.source in self.spec.classes:
                g.add((rel_uri, RDFS.domain, self.REV[rdef.source]))
            if rdef.target in self.spec.classes:
                g.add((rel_uri, RDFS.range, self.REV[rdef.target]))
            g.add((rel_uri, RDFS.label, Literal(rel_name)))
            g.add((rel_uri, RDFS.comment, Literal(rdef.doc)))

        # Datatype Properties
        type_mapping = {
            "string": XSD.string,
            "integer": XSD.integer,
            "int": XSD.integer,
            "decimal": XSD.decimal,
            "float": XSD.decimal,
            "double": XSD.decimal,
            "boolean": XSD.boolean,
            "bool": XSD.boolean,
            "date": XSD.date,
            "timestamptz": XSD.dateTimeStamp,
            "datetime": XSD.dateTime,
        }

        for class_name, cdef in self.spec.classes.items():
            for prop_name, pdef in cdef.properties.items():
                prop_uri = self.REV[prop_name]
                xsd_type = type_mapping.get(pdef.type.lower(), XSD.string)
                g.add((prop_uri, RDF.type, OWL.DatatypeProperty))
                g.add((prop_uri, RDFS.domain, self.REV[class_name]))
                g.add((prop_uri, RDFS.range, xsd_type))
                g.add((prop_uri, RDFS.comment, Literal(pdef.doc)))

        # Serialize directly via rdflib standard Turtle serializer
        return g.serialize(format="turtle")

    # -----------------------------------------------------------------------
    # 2. W3C R2RML Generator (via rdflib.Graph)
    # -----------------------------------------------------------------------
    def generate_r2rml(self) -> str:
        """Construct standard W3C R2RML mappings using native rdflib Graph primitives."""
        rg = Graph()
        rg.bind(self.prefix, self.REV)
        rg.bind("rr", RR)

        # 2a. Base Class Mappings
        for class_name, cdef in self.spec.classes.items():
            map_uri = URIRef(f"{self.ns}#{class_name}Map")

            # rr:logicalTable [ rr:tableName "<table>" ]
            log_table = BNode()
            rg.add((log_table, RR.tableName, Literal(cdef.table)))
            rg.add((map_uri, RR.logicalTable, log_table))

            # rr:subjectMap [ rr:template "http://.../{pk}" ; rr:class :Class ]
            sub_map = BNode()
            template_str = f"{self.ns}{class_name.lower()}/{{{cdef.primary_key}}}"
            rg.add((sub_map, RR.template, Literal(template_str)))
            rg.add((sub_map, RR["class"], self.REV[class_name]))
            rg.add((map_uri, RR.subjectMap, sub_map))

            # rr:predicateObjectMap for each column property
            for p_name in cdef.properties:
                if p_name == cdef.primary_key:
                    continue
                pom = BNode()
                rg.add((pom, RR.predicate, self.REV[p_name]))
                om = BNode()
                rg.add((om, RR.column, Literal(p_name)))
                rg.add((pom, RR.objectMap, om))
                rg.add((map_uri, RR.predicateObjectMap, pom))

            # 2b. Subclass Mappings (with SQL filters)
            for sub_name, sdef in cdef.subclasses.items():
                sub_map_uri = URIRef(f"{self.ns}#{sub_name}Map")
                sub_log_table = BNode()
                sql_query = f"SELECT * FROM {cdef.table} WHERE {sdef.filter}"
                rg.add((sub_log_table, RR.sqlQuery, Literal(sql_query)))
                rg.add((sub_map_uri, RR.logicalTable, sub_log_table))

                sub_subj_map = BNode()
                rg.add((sub_subj_map, RR.template, Literal(template_str)))
                rg.add((sub_subj_map, RR["class"], self.REV[sub_name]))
                rg.add((sub_map_uri, RR.subjectMap, sub_subj_map))

        # 2c. Relationship Mappings (Object Properties / Foreign Key Joins)
        for rel_name, rdef in self.spec.relationships.items():
            if rdef.source not in self.spec.classes or rdef.target not in self.spec.classes:
                continue

            src_class = self.spec.classes[rdef.source]
            tgt_class = self.spec.classes[rdef.target]
            src_pk = src_class.primary_key
            tgt_pk = tgt_class.primary_key

            rel_map_uri = URIRef(f"{self.ns}#{rel_name}Map")
            rel_log_table = BNode()
            join_sql = (
                f"SELECT {src_class.table}.{src_pk}, {tgt_class.table}.{tgt_pk} "
                f"FROM {src_class.table} JOIN {tgt_class.table} ON {rdef.join}"
            )
            rg.add((rel_log_table, RR.sqlQuery, Literal(join_sql)))
            rg.add((rel_map_uri, RR.logicalTable, rel_log_table))

            # Subject is source entity
            src_sub_map = BNode()
            rg.add((src_sub_map, RR.template, Literal(f"{self.ns}{rdef.source.lower()}/{{{src_pk}}}")))
            rg.add((rel_map_uri, RR.subjectMap, src_sub_map))

            # Object is target entity
            rel_pom = BNode()
            rg.add((rel_pom, RR.predicate, self.REV[rel_name]))
            rel_om = BNode()
            rg.add((rel_om, RR.template, Literal(f"{self.ns}{rdef.target.lower()}/{{{tgt_pk}}}")))
            rg.add((rel_pom, RR.objectMap, rel_om))
            rg.add((rel_map_uri, RR.predicateObjectMap, rel_pom))

        return rg.serialize(format="turtle")

    # -----------------------------------------------------------------------
    # 3. Ontop Native OBDA Generator
    # -----------------------------------------------------------------------
    def generate_ontop_obda(self) -> str:
        """Generate native Ontop .obda file (Ontop's proprietary configuration format)."""
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

            # Subclasses with filters
            for sub_name, sdef in cdef.subclasses.items():
                lines.extend([
                    f"mappingId\tMAPPING-SUBCLASS-{sub_name.upper()}",
                    f"target\t\t:{class_name.lower()}/{{{pk}}} a :{sub_name} .",
                    f"source\t\tSELECT * FROM {cdef.table} WHERE {sdef.filter}",
                    "",
                ])

        # Relationship Mappings
        for rel_name, rdef in self.spec.relationships.items():
            if rdef.source not in self.spec.classes or rdef.target not in self.spec.classes:
                continue

            src_class = self.spec.classes[rdef.source]
            tgt_class = self.spec.classes[rdef.target]
            src_pk = src_class.primary_key
            tgt_pk = tgt_class.primary_key

            join_sql = (
                f"SELECT {src_class.table}.{src_pk}, {tgt_class.table}.{tgt_pk} "
                f"FROM {src_class.table} JOIN {tgt_class.table} ON {rdef.join}"
            )

            lines.extend([
                f"mappingId\tMAPPING-REL-{rel_name.upper()}",
                f"target\t\t:{rdef.source.lower()}/{{{src_pk}}} :{rel_name} :{rdef.target.lower()}/{{{tgt_pk}}} .",
                f"source\t\t{join_sql}",
                "",
            ])

        lines.append("]]")
        return "\n".join(lines)


if __name__ == "__main__":
    print("Compiling YAML Ontology into W3C Turtle (.ttl), OBDA (.obda), and R2RML (.r2rml.ttl)...")
    spec = load_ontology_spec()
    gen = OntologyArtifactGenerator(spec)
    result = gen.generate_all()
    print(f"[✓] Successfully compiled and verified:")
    print(f"  • Turtle (.ttl):  {result['turtle_file']} ({result['validated_triples']} triples)")
    print(f"  • R2RML (.r2rml): {result['r2rml_file']} ({result['r2rml_triples']} triples)")
    print(f"  • Ontop (.obda):   {result['obda_file']}")
