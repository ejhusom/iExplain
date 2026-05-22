from __future__ import annotations

from dataclasses import dataclass, field

import requests

from iexplain.intent_graphdb import first_non_null, local_name


@dataclass(slots=True)
class FillRelatedEntity:
    iri: str
    name: str
    kind: str | None = None
    external_id: str | None = None


@dataclass(slots=True)
class FillRelationGroup:
    predicate: str
    entities: list[FillRelatedEntity] = field(default_factory=list)


@dataclass(slots=True)
class FillEntityBundle:
    entity_iri: str
    entity_name: str
    entity_type: str | None
    external_id: str | None
    description: str | None
    outgoing: list[FillRelationGroup]
    incoming: list[FillRelationGroup]


class InGraphFillClient:
    def __init__(
        self,
        base_url: str,
        repository_id: str,
        *,
        resource_prefix: str = "https://intendproject.eu/fill/",
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.repository_id = repository_id
        self.resource_prefix = resource_prefix
        self.timeout_seconds = timeout_seconds
        self.query_url = f"{self.base_url}/query"

    def fetch_entity_bundle(self, entity_id: str) -> FillEntityBundle:
        entity_iri = self._coerce_entity_iri(entity_id)
        entity_rows = self._run_select(self._entity_query(entity_iri))
        outgoing_rows = self._run_select(self._outgoing_query(entity_iri))
        incoming_rows = self._run_select(self._incoming_query(entity_iri))

        if not entity_rows:
            raise ValueError(f"FILL entity not found: {entity_id}")

        return FillEntityBundle(
            entity_iri=entity_iri,
            entity_name=first_non_null(entity_rows, "name") or local_name(entity_iri),
            entity_type=first_non_null(entity_rows, "typeLocal"),
            external_id=first_non_null(entity_rows, "externalId"),
            description=first_non_null(entity_rows, "description"),
            outgoing=_group_relations(outgoing_rows),
            incoming=_group_relations(incoming_rows),
        )

    def _run_select(self, query: str) -> list[dict[str, str]]:
        response = requests.post(
            self.query_url,
            data={
                "repository": self.repository_id,
                "query": query,
                "format": "json",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results")
        if not isinstance(results, dict):
            raise ValueError("inGraph returned an unexpected query payload.")

        rows: list[dict[str, str]] = []
        for binding in results.get("results", {}).get("bindings", []):
            rows.append({key: value["value"] for key, value in binding.items()})
        return rows

    def _coerce_entity_iri(self, entity_id: str) -> str:
        compact = entity_id.strip()
        if compact.startswith("http://") or compact.startswith("https://"):
            return compact
        return f"{self.resource_prefix}{compact}"

    @staticmethod
    def _entity_query(entity_iri: str) -> str:
        return f"""
PREFIX intend: <https://intendproject.eu/schema/>
PREFIX schema: <https://schema.org/>

SELECT DISTINCT ?typeLocal ?name ?externalId ?description
WHERE {{
  BIND(<{entity_iri}> AS ?entity)
  ?entity ?anyPredicate ?anyValue .
  OPTIONAL {{
    ?entity a ?type .
    BIND(REPLACE(STR(?type), "^.*/", "") AS ?typeLocal)
  }}
  OPTIONAL {{ ?entity schema:name ?name . }}
  OPTIONAL {{ ?entity schema:id ?externalId . }}
  OPTIONAL {{ ?entity intend:description ?description . }}
}}
LIMIT 20
"""

    @staticmethod
    def _outgoing_query(entity_iri: str) -> str:
        return f"""
PREFIX schema: <https://schema.org/>

SELECT DISTINCT ?predicateLocal ?neighbor ?neighborType ?neighborName ?neighborExternalId
WHERE {{
  BIND(<{entity_iri}> AS ?entity)
  ?entity ?predicate ?neighbor .
  FILTER(isIRI(?neighbor))
  BIND(REPLACE(STR(?predicate), "^.*/", "") AS ?predicateLocal)
  OPTIONAL {{
    ?neighbor a ?neighborTypeIri .
    BIND(REPLACE(STR(?neighborTypeIri), "^.*/", "") AS ?neighborType)
  }}
  OPTIONAL {{ ?neighbor schema:name ?neighborName . }}
  OPTIONAL {{ ?neighbor schema:id ?neighborExternalId . }}
}}
ORDER BY ?predicateLocal ?neighborName ?neighbor
"""

    @staticmethod
    def _incoming_query(entity_iri: str) -> str:
        return f"""
PREFIX schema: <https://schema.org/>

SELECT DISTINCT ?predicateLocal ?neighbor ?neighborType ?neighborName ?neighborExternalId
WHERE {{
  BIND(<{entity_iri}> AS ?entity)
  ?neighbor ?predicate ?entity .
  FILTER(isIRI(?neighbor))
  BIND(REPLACE(STR(?predicate), "^.*/", "") AS ?predicateLocal)
  OPTIONAL {{
    ?neighbor a ?neighborTypeIri .
    BIND(REPLACE(STR(?neighborTypeIri), "^.*/", "") AS ?neighborType)
  }}
  OPTIONAL {{ ?neighbor schema:name ?neighborName . }}
  OPTIONAL {{ ?neighbor schema:id ?neighborExternalId . }}
}}
ORDER BY ?predicateLocal ?neighborName ?neighbor
"""


def _group_relations(rows: list[dict[str, str]]) -> list[FillRelationGroup]:
    grouped: dict[str, dict[str, FillRelatedEntity]] = {}

    for row in rows:
        predicate = row["predicateLocal"]
        neighbor_iri = row["neighbor"]
        relation_entries = grouped.setdefault(predicate, {})
        relation_entries.setdefault(
            neighbor_iri,
            FillRelatedEntity(
                iri=neighbor_iri,
                name=row.get("neighborName") or local_name(neighbor_iri),
                kind=row.get("neighborType"),
                external_id=row.get("neighborExternalId"),
            ),
        )

    groups: list[FillRelationGroup] = []
    for predicate, entities_by_iri in sorted(grouped.items()):
        entities = sorted(
            entities_by_iri.values(),
            key=lambda item: ((item.kind or ""), item.name, item.iri),
        )
        groups.append(FillRelationGroup(predicate=predicate, entities=entities))
    return groups
