from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import requests


@dataclass(slots=True)
class IntentContext:
    iri: str
    name: str
    description: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class IntentCondition:
    iri: str
    name: str
    description: str | None = None
    metric: str | None = None


@dataclass(slots=True)
class IntentExpectation:
    iri: str
    name: str
    kind: str
    description: str | None = None
    target: str | None = None
    condition_refs: list[str] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IntentReportRecord:
    iri: str
    report_number: int
    generated_at: str
    state: str | None = None
    reason: str | None = None
    handler: str | None = None
    owner: str | None = None


@dataclass(slots=True)
class IntentObservation:
    iri: str
    condition: str | None
    metric: str
    value: float | str
    unit: str | None
    obtained_at: str


@dataclass(slots=True)
class IntentBundle:
    intent_iri: str
    intent_name: str
    handler: str | None
    owner: str | None
    expectations: list[IntentExpectation]
    conditions: list[IntentCondition]
    contexts: list[IntentContext]
    reports: list[IntentReportRecord]
    observations: list[IntentObservation]


class GraphDBIntentClient:
    def __init__(
        self,
        base_url: str,
        repository_id: str,
        *,
        resource_prefix: str = "http://5g4data.eu/5g4data#",
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.repository_id = repository_id
        self.resource_prefix = resource_prefix
        self.timeout_seconds = timeout_seconds
        self.query_url = f"{self.base_url}/repositories/{self.repository_id}"

    def fetch_intent_bundle(self, intent_id: str) -> IntentBundle:
        intent_iri = self._coerce_intent_iri(intent_id)
        bundle_rows = self._run_sparql(self._intent_bundle_query(intent_iri))
        report_rows = self._run_sparql(self._reports_query(intent_iri))
        observation_rows = self._run_sparql(self._observations_query(intent_iri))

        if not bundle_rows and not report_rows and not observation_rows:
            raise ValueError(f"Intent not found: {intent_id}")

        handler = first_non_null(bundle_rows, "intentHandler")
        owner = first_non_null(bundle_rows, "intentOwner")

        expectations: dict[str, IntentExpectation] = {}
        conditions: dict[str, IntentCondition] = {}
        contexts: dict[str, IntentContext] = {}

        for row in bundle_rows:
            expectation_iri = row.get("expectation")
            if expectation_iri:
                expectation = expectations.setdefault(
                    expectation_iri,
                    IntentExpectation(
                        iri=expectation_iri,
                        name=local_name(expectation_iri),
                        kind=local_name(row.get("expectationType")) if row.get("expectationType") else "Expectation",
                        description=row.get("expectationDescription"),
                        target=local_name(row.get("target")) if row.get("target") else None,
                    ),
                )
                condition_iri = row.get("condition")
                if condition_iri and local_name(condition_iri) not in expectation.condition_refs:
                    expectation.condition_refs.append(local_name(condition_iri))
                context_iri = row.get("context")
                if context_iri and local_name(context_iri) not in expectation.context_refs:
                    expectation.context_refs.append(local_name(context_iri))

            condition_iri = row.get("condition")
            if condition_iri:
                conditions.setdefault(
                    condition_iri,
                    IntentCondition(
                        iri=condition_iri,
                        name=local_name(condition_iri),
                        description=row.get("conditionDescription"),
                        metric=local_name(row.get("metric")) if row.get("metric") else None,
                    ),
                )

            context_iri = row.get("context")
            if context_iri:
                context = contexts.setdefault(
                    context_iri,
                    IntentContext(
                        iri=context_iri,
                        name=local_name(context_iri),
                        description=row.get("contextDescription"),
                    ),
                )
                context_property = row.get("contextProperty")
                context_value = row.get("contextValue")
                if context_property and context_value:
                    context.attributes[local_name(context_property)] = compact_value(context_value)

        reports = [
            IntentReportRecord(
                iri=row["report"],
                report_number=int(row["reportNumber"]),
                generated_at=row["generated"],
                state=local_name(row.get("state")) if row.get("state") else None,
                reason=row.get("reason"),
                handler=row.get("handler"),
                owner=row.get("owner"),
            )
            for row in report_rows
        ]
        reports.sort(key=lambda item: item.report_number)

        observations = [
            IntentObservation(
                iri=row["observation"],
                condition=local_name(row.get("condition")) if row.get("condition") else None,
                metric=local_name(row["metric"]),
                value=parse_numeric(row["value"]),
                unit=row.get("unit"),
                obtained_at=row["obtainedAt"],
            )
            for row in observation_rows
        ]
        observations.sort(key=lambda item: item.obtained_at)

        return IntentBundle(
            intent_iri=intent_iri,
            intent_name=local_name(intent_iri),
            handler=handler,
            owner=owner,
            expectations=list(expectations.values()),
            conditions=list(conditions.values()),
            contexts=list(contexts.values()),
            reports=reports,
            observations=observations,
        )

    def _run_sparql(self, query: str) -> list[dict[str, str]]:
        response = requests.post(
            self.query_url,
            data=urlencode({"query": query}),
            headers={
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        rows: list[dict[str, str]] = []
        for binding in payload.get("results", {}).get("bindings", []):
            rows.append({key: value["value"] for key, value in binding.items()})
        return rows

    def _coerce_intent_iri(self, intent_id: str) -> str:
        if intent_id.startswith("http://") or intent_id.startswith("https://"):
            return intent_id
        compact = intent_id.strip()
        if compact.startswith("I"):
            return f"{self.resource_prefix}{compact}"
        return f"{self.resource_prefix}I{compact.replace('-', '')}"

    def _intent_bundle_query(self, intent_iri: str) -> str:
        return f"""
PREFIX data5g: <http://5g4data.eu/5g4data#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX icm: <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/>
PREFIX imo: <http://tio.models.tmforum.org/tio/v3.6.0/IntentManagementOntology/>
PREFIX log: <http://tio.models.tmforum.org/tio/v3.6.0/LogicalOperators/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX set: <http://tio.models.tmforum.org/tio/v3.6.0/SetOperators/>

SELECT ?intentHandler ?intentOwner ?expectation ?expectationType ?expectationDescription ?target
       ?condition ?conditionDescription ?metric
       ?context ?contextDescription ?contextProperty ?contextValue
WHERE {{
  BIND(<{intent_iri}> AS ?intent)
  OPTIONAL {{ ?intent imo:handler ?intentHandler . }}
  OPTIONAL {{ ?intent imo:owner ?intentOwner . }}
  OPTIONAL {{
    ?intent log:allOf ?expectation .
    OPTIONAL {{
      ?expectation a ?expectationType .
      FILTER (?expectationType != icm:IntentElement)
    }}
    OPTIONAL {{ ?expectation dct:description ?expectationDescription . }}
    OPTIONAL {{ ?expectation icm:target ?target . }}
    OPTIONAL {{
      ?expectation log:allOf ?condition .
      ?condition a icm:Condition .
      OPTIONAL {{ ?condition dct:description ?conditionDescription . }}
      OPTIONAL {{
        ?condition set:forAll ?rule .
        ?rule icm:valuesOfTargetProperty ?metric .
      }}
    }}
    OPTIONAL {{
      ?expectation log:allOf ?context .
      ?context a icm:Context .
      OPTIONAL {{ ?context dct:description ?contextDescription . }}
      OPTIONAL {{
        ?context ?contextProperty ?contextValue .
        FILTER (?contextProperty != rdf:type && ?contextProperty != dct:description)
      }}
    }}
  }}
}}
ORDER BY ?expectation ?condition ?context
"""

    def _reports_query(self, intent_iri: str) -> str:
        return f"""
PREFIX icm: <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/>
PREFIX imo: <http://tio.models.tmforum.org/tio/v3.6.0/IntentManagementOntology/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?report ?reportNumber ?generated ?state ?reason ?handler ?owner
WHERE {{
  BIND(<{intent_iri}> AS ?intent)
  ?report a icm:IntentReport ;
          icm:about ?intent ;
          icm:reportNumber ?reportNumber ;
          icm:reportGenerated ?generated .
  OPTIONAL {{ ?report icm:intentHandlingState ?state . }}
  OPTIONAL {{ ?report icm:reason ?reason . }}
  OPTIONAL {{ ?report imo:handler ?handler . }}
  OPTIONAL {{ ?report imo:owner ?owner . }}
}}
ORDER BY xsd:integer(?reportNumber)
"""

    def _observations_query(self, intent_iri: str) -> str:
        return f"""
PREFIX icm: <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/>
PREFIX log: <http://tio.models.tmforum.org/tio/v3.6.0/LogicalOperators/>
PREFIX met: <http://tio.models.tmforum.org/tio/v3.6.0/MetricsAndObservations/>
PREFIX quan: <http://tio.models.tmforum.org/tio/v3.6.0/QuantityOntology/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX set: <http://tio.models.tmforum.org/tio/v3.6.0/SetOperators/>

SELECT ?observation ?condition ?metric ?value ?unit ?obtainedAt
WHERE {{
  BIND(<{intent_iri}> AS ?intent)
  ?intent log:allOf ?expectation .
  ?expectation log:allOf ?condition .
  ?condition a icm:Condition ;
             set:forAll ?rule .
  ?rule icm:valuesOfTargetProperty ?metric .
  ?observation a met:Observation ;
               met:observedMetric ?metric ;
               met:observedValue ?observedValue ;
               met:obtainedAt ?obtainedAt .
  ?observedValue rdf:value ?value .
  OPTIONAL {{ ?observedValue quan:unit ?unit . }}
}}
ORDER BY ?obtainedAt
"""


def local_name(value: str | None) -> str:
    if not value:
        return ""
    if "#" in value:
        return value.rsplit("#", 1)[1]
    if "/" in value:
        return value.rsplit("/", 1)[1]
    return value


def parse_numeric(value: str) -> float | str:
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def first_non_null(rows: list[dict[str, Any]], key: str) -> str | None:
    for row in rows:
        value = row.get(key)
        if value:
            return value
    return None


def compact_value(value: str) -> str:
    if value.startswith("http://5g4data.eu/5g4data#"):
        return local_name(value)
    if value.startswith("http://tio.models.tmforum.org/"):
        return local_name(value)
    if value.startswith("http://www.opengis.net/ont/geosparql#"):
        return local_name(value)
    return value
