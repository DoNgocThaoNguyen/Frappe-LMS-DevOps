#!/usr/bin/env python3
"""Bind a verified GitHub Actions manifest to one Ansible Cloud target."""

import argparse
import json
import re
from pathlib import Path

REPO = "ghcr.io/dongocthaonguyen/dacn-frappe-lms"
RUN_URL = "https://github.com/DoNgocThaoNguyen/DACN-Frappe-LMS/actions/runs/"
SITE = "lms-cloud.localhost"
URL = "http://127.0.0.1:8200/"


def prepare(manifest, stable, run_id):
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("GHA_RUN_ID must be a positive integer")
    if type(manifest.get("run_id")) is not int or manifest["run_id"] != int(run_id):
        raise ValueError("Manifest run_id differs from the approved build parameter")
    if manifest.get("run_url") != RUN_URL + run_id:
        raise ValueError("Manifest run URL differs from the approved run")
    if type(manifest.get("run_attempt")) is not int or manifest["run_attempt"] < 1:
        raise ValueError("Invalid run attempt")
    commit = manifest.get("commit", "")
    if not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Manifest commit is not a full Git SHA")
    ref = manifest.get("image_ref", "")
    if not isinstance(ref, str):
        raise ValueError("Missing image digest reference")
    match = re.fullmatch(re.escape(REPO) + r"@(sha256:[a-f0-9]{64})", ref)
    if match is None:
        raise ValueError("Manifest image reference is not an approved GHCR digest")
    image = REPO + ":sha-" + commit[:12]
    if stable.get("site") != SITE or stable.get("url") != URL:
        raise ValueError("Stable site or URL changed")
    if not isinstance(stable.get("image"), str) or not re.fullmatch(
        re.escape(REPO) + r":sha-[a-f0-9]{12}", stable["image"]
    ):
        raise ValueError("Invalid stable image")
    if not isinstance(stable.get("digest"), str) or not re.fullmatch(
        r"sha256:[a-f0-9]{64}", stable["digest"]
    ):
        raise ValueError("Invalid stable digest")
    if image == stable["image"]:
        raise ValueError("Candidate is already the stable release")
    return {
        "cloud_deploy_approved": True,
        "target": {
            "image": image,
            "digest": match.group(1),
            "site": stable["site"],
            "url": stable["url"],
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--stable", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release = prepare(
        json.loads(args.manifest.read_text()),
        json.loads(args.stable.read_text()),
        args.run_id,
    )
    args.output.write_text(json.dumps(release, indent=2) + "\n")
    args.output.chmod(0o600)
    print("Verified approved candidate:", release["target"]["image"])


if __name__ == "__main__":
    main()
