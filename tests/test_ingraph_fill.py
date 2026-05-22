from __future__ import annotations

from iexplain.ingraph_fill import InGraphFillClient
from iexplain.runtime.pipelines import get_pipeline
from iexplain.runtime.tools import ToolContext, build_tools


class StubFillClient(InGraphFillClient):
    def __init__(self) -> None:
        super().__init__("http://localhost:5000", "FILL")

    def _run_select(self, query: str) -> list[dict[str, str]]:
        if "?entity ?predicate ?neighbor" in query:
            return [
                {
                    "predicateLocal": "hasContainer",
                    "neighbor": "https://intendproject.eu/fill/Container1",
                    "neighborType": "Container",
                    "neighborName": "Container1",
                    "neighborExternalId": "ID161124_Container1",
                },
                {
                    "predicateLocal": "hasContainer",
                    "neighbor": "https://intendproject.eu/fill/Container5",
                    "neighborType": "Container",
                    "neighborName": "Container5",
                    "neighborExternalId": "ID161124_Container5",
                },
                {
                    "predicateLocal": "hasService",
                    "neighbor": "https://intendproject.eu/fill/Service3",
                    "neighborType": "Service",
                    "neighborName": "Service3",
                    "neighborExternalId": "ID161124_Service3",
                },
            ]
        if "?neighbor ?predicate ?entity" in query:
            return [
                {
                    "predicateLocal": "canBeDeployedOn",
                    "neighbor": "https://intendproject.eu/fill/Container6",
                    "neighborType": "Container",
                    "neighborName": "Container6",
                    "neighborExternalId": "ID161124_Container6",
                },
                {
                    "predicateLocal": "canBeDeployedOn",
                    "neighbor": "https://intendproject.eu/fill/Container19",
                    "neighborType": "Container",
                    "neighborName": "Container19",
                    "neighborExternalId": "ID161124_Container19",
                },
            ]
        return [
            {
                "typeLocal": "Machine",
                "name": "Machine5",
                "externalId": "ID161124_Machine5",
            }
        ]


def test_fetch_fill_entity_bundle_normalizes_direct_relationships():
    client = StubFillClient()

    bundle = client.fetch_entity_bundle("Machine5")

    assert bundle.entity_iri == "https://intendproject.eu/fill/Machine5"
    assert bundle.entity_name == "Machine5"
    assert bundle.entity_type == "Machine"
    assert bundle.external_id == "ID161124_Machine5"
    assert [group.predicate for group in bundle.outgoing] == ["hasContainer", "hasService"]
    assert [entity.name for entity in bundle.outgoing[0].entities] == ["Container1", "Container5"]
    assert [group.predicate for group in bundle.incoming] == ["canBeDeployedOn"]
    assert [entity.name for entity in bundle.incoming[0].entities] == ["Container19", "Container6"]


def test_fetch_fill_entity_bundle_tool_returns_compact_payload(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self, base_url: str, repository_id: str, *, resource_prefix: str, timeout_seconds: int = 30):
            assert base_url == "http://localhost:5000"
            assert repository_id == "FILL"
            assert resource_prefix == "https://intendproject.eu/fill/"

        def fetch_entity_bundle(self, entity_id: str):
            assert entity_id == "Machine5"
            return StubFillClient().fetch_entity_bundle(entity_id)

    monkeypatch.setattr("iexplain.runtime.tools.InGraphFillClient", FakeClient)
    tools = build_tools(["fetch_fill_entity_bundle"], ToolContext(tmp_path))
    result = tools["fetch_fill_entity_bundle"].call({"entity_id": "Machine5"})

    assert result["entity_name"] == "Machine5"
    assert result["entity_type"] == "Machine"
    assert result["counts"]["outgoing_relations"] == 2
    assert result["counts"]["incoming_entities"] == 2
    assert result["outgoing"][1]["predicate"] == "hasService"
    assert result["incoming"][0]["entities"][0]["name"] == "Container19"
    assert get_pipeline("ingraph_fill_summary")[0].tools == ["fetch_fill_entity_bundle"]
