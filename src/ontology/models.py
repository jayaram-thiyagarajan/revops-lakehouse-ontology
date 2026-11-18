"""Pydantic data models for RevOps Ontology specification."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PropertyDef(BaseModel):
    type: str
    doc: str


class SubclassDef(BaseModel):
    filter: str
    doc: str


class ClassDef(BaseModel):
    description: str
    table: str
    primary_key: str
    properties: Dict[str, PropertyDef] = Field(default_factory=dict)
    subclasses: Dict[str, SubclassDef] = Field(default_factory=dict)


class RelationshipDef(BaseModel):
    source: str
    target: str
    join: str
    inverse: Optional[str] = None
    doc: str


class MetricDef(BaseModel):
    name: str
    source_concept: str
    description: str
    formula: Optional[str] = None
    sql_expression: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    group_by: Optional[List[str]] = None


class OntologyMeta(BaseModel):
    name: str
    namespace: str
    prefix: str
    description: str


class OntologySpec(BaseModel):
    ontology: OntologyMeta
    classes: Dict[str, ClassDef]
    relationships: Dict[str, RelationshipDef]
    metrics: Dict[str, MetricDef] = Field(default_factory=dict)

