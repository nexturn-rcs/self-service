#!/usr/bin/env python3
"""Update ServiceNow RITM status/comments from GitHub Actions."""

import argparse
import os
from datetime import datetime, timezone

import requests
from requests.auth import HTTPBasicAuth


def get_env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def resolve_ritm_sys_id(base_url: str, auth: HTTPBasicAuth, ritm_sys_id: str, ritm_number: str) -> str:
    if ritm_sys_id:
        return ritm_sys_id

    if not ritm_number:
        raise ValueError("Either RITM_SYS_ID or RITM_NUMBER must be provided")

    resp = requests.get(
        f"{base_url}/api/now/table/sc_req_item",
        auth=auth,
        headers={"Accept": "application/json"},
        params={
            "sysparm_query": f"number={ritm_number}",
            "sysparm_fields": "sys_id",
            "sysparm_limit": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json().get("result", [])
    if not result:
        raise RuntimeError(f"RITM not found for number: {ritm_number}")
    return result[0]["sys_id"]


def patch_ritm(base_url: str, auth: HTTPBasicAuth, ritm_sys_id: str, payload: dict) -> None:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    url = f"{base_url}/api/now/table/sc_req_item/{ritm_sys_id}"

    # Separate journal fields from state fields â€” ServiceNow sometimes
    # drops journal writes when combined with state transitions
    journal_fields = {}
    state_fields = {}
    for k, v in payload.items():
        if k in ("comments", "work_notes"):
            journal_fields[k] = v
        else:
            state_fields[k] = v

    # First: update state
    if state_fields:
        resp = requests.patch(url, auth=auth, headers=headers, json=state_fields, timeout=30)
        resp.raise_for_status()

    # Second: write comments/work_notes
    if journal_fields:
        resp = requests.patch(url, auth=auth, headers=headers, json=journal_fields, timeout=30)
        resp.raise_for_status()


def build_payload(mode: str, repo_name: str) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    repo_url = f"https://github.com/nexturn-rcs/{repo_name}"

    if mode == "in_progress":
        return {
            "state": "2",  # Work in Progress
            "work_notes": (
                f"Repository creation in progress.\n"
                f"Repository: nexturn-rcs/{repo_name}\n"
                f"Started at: {stamp}"
            ),
            "comments": (
                "Your request has been approved and repository creation is now in progress. "
                "Our platform automation is building your repository. "
                "You will be notified once it is ready."
            ),
        }

    if mode == "success":
        return {
            "state": "3",  # Closed Complete
            "close_notes": f"Repository created successfully: {repo_url}",
            "work_notes": (
                f"Repository provisioning completed successfully.\n"
                f"Repository URL : {repo_url}\n"
                f"Default Branch : develop\n"
                f"Completed at   : {stamp}\n"
                f"Organization   : nexturn-rcs"
            ),
            "comments": (
                f"Great news! Your repository has been created successfully "
                f"and is ready to use.\n\n"
                f"Repository : {repo_url}\n"
                f"Branch     : develop\n\n"
                f"Your new repository includes:\n"
                f"  - Production-ready Python starter code\n"
                f"  - Enabled Dockerization\n"
                f"  - Helm chart for AKS deployment\n"
                f"  - CI/CD pipeline workflows\n"
                f"  - Azure credentials pre-configured\n\n"
                f"Refer to the Actions tab in GitHub for workflow runs: "
                f"https://github.com/nexturn-rcs/{repo_name}/actions\n\n"
                f"Contact us at platformsupport@nexturn.com in case of run failures.\n\n"
                f"Happy coding!"
            ),
        }

    if mode == "failed":
        return {
            "state": "2",  # Work in Progress
            "work_notes": (
                f"Repository creation FAILED in platform automation pipeline.\n"
                f"Target repository: nexturn-rcs/{repo_name}\n"
                f"Failed at: {stamp}\n"
                f"Action required: Platform team investigation needed.\n"
                f"Ticket placed On Hold pending resolution."
            ),
            "comments": (
                "Unfortunately, repository creation has failed. "
                "Please check with Platform Team DL: platformsupport@nexturn.com\n\n"
                "The platform team has been notified and will investigate. "
                "This ticket has been placed On Hold until the issue is resolved. "
                "You do not need to raise a separate ticket."
            ),
        }

    raise ValueError(f"Unsupported mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update ServiceNow RITM from workflow")
    parser.add_argument(
        "--mode", choices=["in_progress", "success", "failed"], required=True)
    args = parser.parse_args()

    base_url = get_env("SNOW_INSTANCE_URL")
    username = get_env("SNOW_USERNAME")
    password = get_env("SNOW_PASSWORD")
    repo_name = get_env("REPO_NAME")
    ritm_number = get_env("RITM_NUMBER", required=False)
    ritm_sys_id = get_env("RITM_SYS_ID", required=False)

    auth = HTTPBasicAuth(username, password)
    resolved_sys_id = resolve_ritm_sys_id(
        base_url, auth, ritm_sys_id, ritm_number)
    payload = build_payload(args.mode, repo_name)

    patch_ritm(base_url, auth, resolved_sys_id, payload)
    print(
        f"Updated RITM {ritm_number or resolved_sys_id} with mode={args.mode}")


if __name__ == "__main__":
    main()
