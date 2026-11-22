
#!/usr/bin/env python3
"""Read-only deployment checks for a DACN Frappe LMS staging site."""

import argparse
import json
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ValidationError(Exception):
    """One required deployment check did not pass."""


def command(args, timeout=20):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True,
            check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationError(f"Cannot run {args[0]}: {exc}") from exc

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise ValidationError(
            f"Command {args[0]} failed: {details[:350]}"
        )

    return result.stdout.strip()


def check_container(name, expected_image):
    state = command([
        "docker", "inspect", "--format",
        "{{.State.Running}}|{{.Config.Image}}", name
    ])

    try:
        running, actual_image = state.split("|", 1)
    except ValueError as exc:
        raise ValidationError(
            f"Unexpected docker inspect result for {name}"
        ) from exc

    if running != "true":
        raise ValidationError(f"{name} is not running")

    if actual_image != expected_image:
        raise ValidationError(
            f"{name} image mismatch: "
            f"expected {expected_image}; got {actual_image}"
        )

    print(f"PASS container: {name} is running with expected image")


def check_digest(expected_image, expected_digest):
    raw = command([
        "docker", "image", "inspect", "--format",
        "{{json .RepoDigests}}", expected_image
    ])

    try:
        digests = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "Cannot parse image repository digests"
        ) from exc

    if not isinstance(digests, list) or not any(
        item.endswith("@" + expected_digest) for item in digests
    ):
        raise ValidationError(
            "Image digest differs from expected release digest"
        )

    print(f"PASS image digest: {expected_digest}")


def check_http(url, site, timeout):
    request = Request(
        url,
        headers={
            "Host": site,
            "User-Agent": "DACN-Validator/1.0"
        }
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValidationError(f"HTTP check failed: {exc}") from exc

    if status != 200:
        raise ValidationError(
            f"HTTP returned {status}, expected 200"
        )

    print(f"PASS HTTP: {url} returned 200")


def check_apps(backend, site):
    output = command([
        "docker", "exec", backend,
        "bench", "--site", site,
        "list-apps", "--format", "text"
    ], timeout=50)

    installed = {
        line.split()[0].lower()
        for line in output.splitlines()
        if line.split()
    }

    needed = {"frappe", "payments", "lms"}
    missing = needed - installed

    if missing:
        raise ValidationError(
            f"Site missing required app(s): "
            f"{', '.join(sorted(missing))}"
        )

    print("PASS installed apps: frappe, payments, lms")


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--expected-digest")
    parser.add_argument(
        "--backend", default="dacn-staging-backend-1"
    )
    parser.add_argument(
        "--frontend", default="dacn-staging-frontend-1"
    )
    parser.add_argument(
        "--site", default="lms-staging.localhost"
    )
    parser.add_argument(
        "--url", default="http://127.0.0.1:8200/"
    )
    parser.add_argument("--timeout", type=float, default=10.0)

    args = parser.parse_args()

    try:
        check_container(args.backend, args.expected_image)
        check_container(args.frontend, args.expected_image)

        if args.expected_digest:
            check_digest(
                args.expected_image,
                args.expected_digest
            )

        check_apps(args.backend, args.site)
        check_http(args.url, args.site, args.timeout)

    except ValidationError as exc:
        print(
            f"DEPLOYMENT VALIDATION: FAIL - {exc}",
            file=sys.stderr
        )
        return 1

    print("DEPLOYMENT VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
