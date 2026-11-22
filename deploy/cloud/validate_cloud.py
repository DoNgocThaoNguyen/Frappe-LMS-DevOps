#!/usr/bin/env python3
"""Read-only validation of the DACN Frappe LMS Cloud deployment on EC2.

Runs ON the EC2 host as root (via Ansible become), without changing Docker/DB.
Requires validate_deployment.py next to this file.
"""

import argparse
import sys

from validate_deployment import (ValidationError, check_apps, check_digest,
                                 check_http, command)

APP_SERVICES = (
    "backend", "frontend", "websocket", "queue-short", "queue-long", "scheduler"
)


def check_service(project, service, expected_image, expected_id):
    name = f"{project}-{service}-1"
    raw = command([
        "docker", "inspect", "--format",
        "{{.State.Running}}|{{.Config.Image}}|{{.Image}}", name
    ])
    try:
        running, image, image_id = raw.split("|", 2)
    except ValueError as exc:
        raise ValidationError(f"Malformed docker inspect for {name}") from exc
    if running != "true":
        raise ValidationError(f"Container not running: {name}")
    if image != expected_image:
        raise ValidationError(
            f"Image tag mismatch on {name}: expected {expected_image}, got {image}"
        )
    if image_id != expected_id:
        raise ValidationError(f"Running image ID mismatch on {name}")
    print(f"PASS service {service}: running, tag + image ID verified")


def check_db_and_redis(project):
    name = f"{project}-db-1"
    health = command([
        "docker", "inspect", "--format", "{{.State.Health.Status}}", name
    ])
    if health != "healthy":
        raise ValidationError(f"MariaDB not healthy: {health}")
    print("PASS MariaDB: healthy")
    for service in ("redis-cache", "redis-queue"):
        name = f"{project}-{service}-1"
        result = command(["docker", "exec", name, "redis-cli", "ping"])
        if result != "PONG":
            raise ValidationError(f"{service} PING returned: {result}")
        print(f"PASS {service}: PONG")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-image", required=True)
    p.add_argument("--expected-digest", required=True)
    p.add_argument("--site", default="lms-cloud.localhost")
    p.add_argument("--url", default="http://127.0.0.1:8200/")
    p.add_argument("--project", default="dacn-cloud")
    p.add_argument("--timeout", type=float, default=15.0)
    args = p.parse_args()
    try:
        # A tag and repository digest are validated BEFORE app-service checks.
        check_digest(args.expected_image, args.expected_digest)
        expected_id = command([
            "docker", "image", "inspect", "--format", "{{.Id}}",
            args.expected_image
        ])
        if not expected_id.startswith("sha256:"):
            raise ValidationError("Docker returned an invalid image ID")
        for service in APP_SERVICES:
            check_service(args.project, service, args.expected_image, expected_id)
        check_db_and_redis(args.project)
        check_apps(f"{args.project}-backend-1", args.site)
        check_http(args.url, args.site, args.timeout)
    except ValidationError as exc:
        print(f"CLOUD DEPLOYMENT VALIDATION: FAIL - {exc}", file=sys.stderr)
        return 1
    print("CLOUD DEPLOYMENT VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
