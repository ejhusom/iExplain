from __future__ import annotations

from iexplain.intent_graphdb import GraphDBIntentClient, compact_value, local_name


class StubIntentClient(GraphDBIntentClient):
    def __init__(self) -> None:
        super().__init__("http://localhost:7200", "intents_and_intent_reports")

    def _run_sparql(self, query: str) -> list[dict[str, str]]:
        if "SELECT ?report ?reportNumber" in query:
            return [
                {
                    "report": "http://5g4data.eu/5g4data#RP1002",
                    "reportNumber": "2",
                    "generated": "2026-03-17T09:07:00Z",
                    "state": "http://tio.models.tmforum.org/tio/v3.6.0/IntentManagementOntology/StateDegraded",
                    "reason": "Compute latency exceeded the declared threshold after deployment rollout in EC21.",
                    "handler": "inOrch",
                    "owner": "inSwitch",
                },
                {
                    "report": "http://5g4data.eu/5g4data#RP1003",
                    "reportNumber": "3",
                    "generated": "2026-03-17T09:18:00Z",
                    "state": "http://tio.models.tmforum.org/tio/v3.6.0/IntentManagementOntology/StateCompliant",
                    "reason": "Workload moved to a less loaded node and compute latency recovered.",
                    "handler": "inOrch",
                    "owner": "inSwitch",
                },
            ]
        if "SELECT ?observation ?condition ?metric" in query:
            return [
                {
                    "observation": "http://5g4data.eu/5g4data#OBS1001",
                    "condition": "http://5g4data.eu/5g4data#CO9aa045ce3c784d9ca12ab3d029059afd",
                    "metric": "http://5g4data.eu/5g4data#computelatency_CO9aa045ce3c784d9ca12ab3d029059afd",
                    "value": "132.0",
                    "unit": "ms",
                    "obtainedAt": "2026-03-17T09:06:00Z",
                }
            ]
        return [
            {
                "intentHandler": "inOrch",
                "intentOwner": "inSwitch",
                "expectation": "http://5g4data.eu/5g4data#DE47aad4bcf64d4b78aa5d30c49076e63b",
                "expectationType": "http://5g4data.eu/5g4data#DeploymentExpectation",
                "expectationDescription": "Deploy AI inference service to edge datacenter",
                "target": "http://5g4data.eu/5g4data#deployment",
                "condition": "http://5g4data.eu/5g4data#CO9aa045ce3c784d9ca12ab3d029059afd",
                "conditionDescription": "Compute latency condition quan:smaller: 1000ms",
                "metric": "http://5g4data.eu/5g4data#computelatency_CO9aa045ce3c784d9ca12ab3d029059afd",
                "context": "http://5g4data.eu/5g4data#CXe5deca8bbcce4e6d9afd7a12318178bf",
                "contextDescription": "Context for datacenter: EC21, application: ai-inference-service",
                "contextProperty": "http://5g4data.eu/5g4data#DataCenter",
                "contextValue": "EC21",
            },
            {
                "intentHandler": "inOrch",
                "intentOwner": "inSwitch",
                "expectation": "http://5g4data.eu/5g4data#DE47aad4bcf64d4b78aa5d30c49076e63b",
                "expectationType": "http://5g4data.eu/5g4data#DeploymentExpectation",
                "expectationDescription": "Deploy AI inference service to edge datacenter",
                "target": "http://5g4data.eu/5g4data#deployment",
                "condition": "http://5g4data.eu/5g4data#CO9aa045ce3c784d9ca12ab3d029059afd",
                "conditionDescription": "Compute latency condition quan:smaller: 1000ms",
                "metric": "http://5g4data.eu/5g4data#computelatency_CO9aa045ce3c784d9ca12ab3d029059afd",
                "context": "http://5g4data.eu/5g4data#CXe5deca8bbcce4e6d9afd7a12318178bf",
                "contextDescription": "Context for datacenter: EC21, application: ai-inference-service",
                "contextProperty": "http://5g4data.eu/5g4data#Application",
                "contextValue": "ai-inference-service",
            },
        ]


def test_fetch_intent_bundle_normalizes_expectations_reports_and_context():
    client = StubIntentClient()

    bundle = client.fetch_intent_bundle("f9587ca0-40be-457d-908d-54e7aecc2ef6")

    assert bundle.intent_name == "If9587ca040be457d908d54e7aecc2ef6"
    assert bundle.handler == "inOrch"
    assert bundle.owner == "inSwitch"
    assert [item.name for item in bundle.expectations] == ["DE47aad4bcf64d4b78aa5d30c49076e63b"]
    assert [item.name for item in bundle.conditions] == ["CO9aa045ce3c784d9ca12ab3d029059afd"]
    assert bundle.contexts[0].attributes == {
        "DataCenter": "EC21",
        "Application": "ai-inference-service",
    }
    assert [report.report_number for report in bundle.reports] == [2, 3]
    assert bundle.reports[0].state == "StateDegraded"
    assert bundle.observations[0].value == 132.0
    assert bundle.observations[0].metric == "computelatency_CO9aa045ce3c784d9ca12ab3d029059afd"


def test_local_name_handles_iris_and_literals():
    assert local_name("http://5g4data.eu/5g4data#DataCenter") == "DataCenter"
    assert local_name("https://example.com/foo/bar") == "bar"
    assert local_name("plain-text") == "plain-text"


def test_compact_value_preserves_external_urls():
    assert compact_value("http://5g4data.eu/5g4data#EC21") == "EC21"
    assert compact_value("http://intend.eu/5G4DataWorkloadCatalogue/ai-inference-deployment.yaml") == (
        "http://intend.eu/5G4DataWorkloadCatalogue/ai-inference-deployment.yaml"
    )
