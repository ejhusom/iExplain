from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import PurePosixPath
from pathlib import Path
from textwrap import dedent
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DEFAULT_REPOSITORY = "intents_and_intent_reports"
DEFAULT_GRAPHDB_URL = "http://localhost:7200"
DEFAULT_ONTOLOGY_CANDIDATE = (
    ROOT.parents[2]
    / "5G4Data-private"
    / "TM-Forum-Intent-Toolkit"
    / "TMForumIntentOntology"
    / "catenated"
    / "tmForumOntologyCompleteV3.6.0.nq"
)


def request(
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, bytes]:
    req = Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=timeout) as response:
        return response.status, response.read()


def wait_for_graphdb(base_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    status_url = urljoin(base_url.rstrip("/") + "/", "rest/repositories")
    while time.time() < deadline:
        try:
            status, _ = request("GET", status_url, headers={"Accept": "application/json"}, timeout=5)
            if status == 200:
                return
        except (HTTPError, URLError):
            time.sleep(2)
    raise RuntimeError(f"GraphDB did not become ready within {timeout_seconds} seconds.")


def repository_exists(base_url: str, repository: str) -> bool:
    status, body = request(
        "GET",
        urljoin(base_url.rstrip("/") + "/", "rest/repositories"),
        headers={"Accept": "application/json"},
    )
    if status != 200:
        raise RuntimeError(f"Failed to list repositories: HTTP {status}")
    repositories = json.loads(body.decode("utf-8"))
    return repository in repositories


def create_repository(base_url: str, repository: str) -> None:
    compose_args = ["docker", "compose", "-f", str(ROOT / "compose.yaml")]
    template_name = f"intentlab-{repository}"
    container_template = PurePosixPath("/opt/graphdb/dist/configs/templates") / f"{template_name}.ttl"
    config = repository_config_ttl(repository)

    subprocess.run(
        compose_args + ["exec", "-T", "graphdb", "sh", "-lc", f"cat > {container_template}"],
        input=config.encode("utf-8"),
        check=True,
    )
    subprocess.run(
        compose_args
        + [
            "exec",
            "-T",
            "graphdb",
            "sh",
            "-lc",
            (
                f'printf "create {template_name}\\nexit\\n" '
                "| /opt/graphdb/dist/bin/console -q -f -s http://localhost:7200"
            ),
        ],
        check=True,
    )


def delete_repository(base_url: str, repository: str) -> None:
    compose_args = ["docker", "compose", "-f", str(ROOT / "compose.yaml")]
    subprocess.run(
        compose_args
        + [
            "exec",
            "-T",
            "graphdb",
            "sh",
            "-lc",
            (
                f'printf "drop {repository}\\nexit\\n" '
                "| /opt/graphdb/dist/bin/console -q -f -s http://localhost:7200"
            ),
        ],
        check=True,
    )


def upload_rdf(base_url: str, repository: str, rdf_path: Path) -> None:
    suffix = rdf_path.suffix.lower()
    if suffix == ".ttl":
        content_type = "application/x-turtle"
    elif suffix == ".nq":
        content_type = "application/n-quads"
    else:
        raise RuntimeError(f"Unsupported RDF file type: {rdf_path}")
    status, body = request(
        "POST",
        urljoin(base_url.rstrip("/") + "/", f"repositories/{repository}/statements"),
        data=rdf_path.read_bytes(),
        headers={"Content-Type": content_type},
        timeout=120,
    )
    if status not in {200, 201, 204}:
        raise RuntimeError(f"Failed to upload {rdf_path.name}: HTTP {status} {body.decode('utf-8', errors='ignore')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a local GraphDB with sample TM Forum intents and reports.")
    parser.add_argument("--graphdb-url", default=DEFAULT_GRAPHDB_URL, help="GraphDB base URL.")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY, help="Repository name to seed.")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds to wait for GraphDB readiness.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the repository first if it already exists.",
    )
    parser.add_argument(
        "--ontology-path",
        default="auto",
        help="Path to the TM Forum ontology bundle (.nq). Use 'skip' to avoid loading it.",
    )
    return parser.parse_args()


def repository_config_ttl(repository: str) -> str:
    return dedent(
        f"""\
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
        @prefix rep: <http://www.openrdf.org/config/repository#>.
        @prefix sr: <http://www.openrdf.org/config/repository/sail#>.
        @prefix sail: <http://www.openrdf.org/config/sail#>.
        @prefix graphdb: <http://www.ontotext.com/config/graphdb#>.
        [] a rep:Repository ;
            rep:repositoryID "{repository}" ;
            rdfs:label "{repository} Repository" ;
            rep:repositoryImpl [
                rep:repositoryType "graphdb:SailRepository" ;
                sr:sailImpl [
                    sail:sailType "graphdb:Sail" ;
                    graphdb:read-only "false" ;
                    graphdb:ruleset "owl-horst-optimized" ;
                    graphdb:disable-sameAs "true" ;
                    graphdb:check-for-inconsistencies "false" ;
                    graphdb:entity-id-size "32" ;
                    graphdb:enable-context-index "false" ;
                    graphdb:enablePredicateList "true" ;
                    graphdb:enable-fts-index "false" ;
                    graphdb:query-timeout "0" ;
                    graphdb:query-limit-results "0" ;
                    graphdb:base-URL "http://example.org/owlim#" ;
                    graphdb:repository-type "file-repository" ;
                    graphdb:storage-folder "storage" ;
                    graphdb:entity-index-size "10000000" ;
                    graphdb:in-memory-literal-properties "true" ;
                    graphdb:enable-literal-index "true" ;
                ]
            ].
        """
    )


def resolve_ontology_path(value: str) -> Path | None:
    if value == "skip":
        return None
    if value != "auto":
        return Path(value).expanduser().resolve()
    if DEFAULT_ONTOLOGY_CANDIDATE.exists():
        return DEFAULT_ONTOLOGY_CANDIDATE
    return None


def main() -> int:
    args = parse_args()
    graphdb_url = args.graphdb_url.rstrip("/")
    sample_dir = ROOT / "sample_data"
    ontology_path = resolve_ontology_path(args.ontology_path)

    print(f"Waiting for GraphDB at {graphdb_url} ...")
    wait_for_graphdb(graphdb_url, args.timeout)

    if repository_exists(graphdb_url, args.repository):
        if args.reset:
            print(f"Deleting repository {args.repository} ...")
            delete_repository(graphdb_url, args.repository)
            time.sleep(2)
            print(f"Creating repository {args.repository} ...")
            create_repository(graphdb_url, args.repository)
        else:
            print(f"Repository {args.repository} already exists.")
    else:
        print(f"Creating repository {args.repository} ...")
        create_repository(graphdb_url, args.repository)

    if ontology_path is not None:
        if not ontology_path.exists():
            raise RuntimeError(f"Ontology file not found: {ontology_path}")
        print(f"Uploading ontology from {ontology_path} ...")
        upload_rdf(graphdb_url, args.repository, ontology_path)
    else:
        print("Skipping ontology upload.")

    for rdf_file in [sample_dir / "sample_intents.ttl", sample_dir / "sample_reports.ttl"]:
        print(f"Uploading {rdf_file.name} ...")
        upload_rdf(graphdb_url, args.repository, rdf_file)

    print()
    print("Local intent GraphDB is ready.")
    print(f"GraphDB UI: {graphdb_url}")
    print(f"Repository: {args.repository}")
    print("Seeded sample intents:")
    print("- Ia1e473dc2526467faf503790412ea648")
    print("- If9587ca040be457d908d54e7aecc2ef6")
    print("- I394dd36b9e57452399fb75bcf6f2d453")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
