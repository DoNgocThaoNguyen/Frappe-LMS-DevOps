"""Read the tested image reference for a GitHub Actions run. Write JSON to stdout."""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPOSITORY = "DoNgocThaoNguyen/DACN-Frappe-LMS"
WORKFLOW = "dacn-frappe-tests.yml"
IMAGE = f"ghcr.io/{REPOSITORY.lower()}"
MANIFEST_NAME = "release-candidate.json"
MAX_BYTES = 4 * 1024 * 1024  # The endpoints return metadata or a ZIP with one JSON file.


def fetch(path, token):
    request = Request(f"https://api.github.com/repos/{REPOSITORY}/actions/{path}", headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "dacn-release-digest",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    # A ZIP download redirects to storage. Only the original API request uses the PAT.
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise ValueError(f"GitHub HTTP {exc.code} while reading {path}") from None
    except (URLError, OSError) as exc:
        raise ValueError(f"Could not read {path} ({type(exc).__name__})") from None
    if len(data) > MAX_BYTES:
        raise ValueError(f"Oversized response while reading {path}")
    return data


def validate_manifest(manifest, run):
    if not isinstance(manifest, dict):
        raise ValueError("Expected a JSON object in the release manifest")
    expected = {
        "commit": run["head_sha"],
        "run_id": run["id"],
        "run_attempt": run["run_attempt"],
        "run_url": run["html_url"],
    }
    for key, value in expected.items():
        actual = manifest.get(key)
        if type(actual) is not type(value) or actual != value:
            raise ValueError(f"Manifest field does not match the run: {key}")
    image_ref = manifest.get("image_ref")
    if not isinstance(image_ref, str) or not re.fullmatch(
        re.escape(IMAGE) + r"@sha256:[0-9a-f]{64}", image_ref
    ):
        raise ValueError(f"Expected a sha256 digest reference for {IMAGE}")
    return {**expected, "image_ref": image_ref}


def read_candidate(run_id, token):
    run_path = f"runs/{run_id}"
    run = json.loads(fetch(run_path, token))
    workflow = json.loads(fetch(f"workflows/{WORKFLOW}", token))
    if run["id"] != run_id or run["workflow_id"] != workflow["id"]:
        raise ValueError(f"Expected run {run_id} of {WORKFLOW}")
    if run["event"] != "workflow_dispatch" or run["head_branch"] != "main":
        raise ValueError("Expected a manually triggered run on main")
    if run["status"] != "completed" or run["conclusion"] != "success":
        raise ValueError(f"Run {run_id} is {run['status']}/{run['conclusion']}")

    # Select one successful attempt, even if a later rerun is started during the download.
    attempt = run["run_attempt"]
    if type(attempt) is not int or attempt < 1:
        raise ValueError("Invalid run_attempt returned by GitHub")
    name = f"release-candidate-{run_id}-{attempt}"
    listing = json.loads(fetch(f"{run_path}/artifacts?name={name}", token))
    matches = [a for a in listing["artifacts"] if a["name"] == name and a["expired"] is False]
    if len(matches) != 1:
        raise ValueError(f"Expected one unexpired artifact named {name}, found {len(matches)}")
    artifact = matches[0]
    archive = fetch(f"artifacts/{int(artifact['id'])}/zip", token)
    # GitHub's artifact digest identifies the ZIP, independently of the Docker image digest.
    zip_digest = artifact.get("digest")
    if zip_digest is not None and zip_digest != "sha256:" + hashlib.sha256(archive).hexdigest():
        raise ValueError("ZIP checksum does not match the GitHub artifact digest")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        members = [m for m in bundle.infolist() if m.filename == MANIFEST_NAME]
        if len(members) != 1 or members[0].file_size > MAX_BYTES:
            raise ValueError(f"Expected one readable {MANIFEST_NAME} in {name}")
        with bundle.open(members[0]) as stream:
            candidate = validate_manifest(json.load(stream), run)
    print(f"VERIFIED {name} commit={candidate['commit']} image={candidate['image_ref']}", file=sys.stderr)
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=int, help="numeric ID from the GitHub Actions run URL")
    args = parser.parse_args()
    if args.run_id < 1:
        parser.error("run_id must be a positive integer")
    token = os.environ.get("GH_TOKEN")
    if not token:
        parser.exit(1, "Missing GH_TOKEN from Jenkins credentials\n")
    try:
        candidate = read_candidate(args.run_id, token)
    except (ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Release candidate verification failed: {exc}\n")
    print(json.dumps(candidate, indent=2))


if __name__ == "__main__":
    main()
