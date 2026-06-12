#!/usr/bin/env python3
"""Update ServiceNow RITM for Azure Infrastructure requests."""

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
        params={"sysparm_query": f"number={ritm_number}", "sysparm_fields": "sys_id", "sysparm_limit": 1},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json().get("result", [])
    if not result:
        raise RuntimeError(f"RITM not found: {ritm_number}")
    return result[0]["sys_id"]


def patch_ritm(base_url: str, auth: HTTPBasicAuth, ritm_sys_id: str, payload: dict) -> None:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    url = f"{base_url}/api/now/table/sc_req_item/{ritm_sys_id}"

    # Separate state fields from journal fields to avoid drops
    journal = {k: v for k, v in payload.items() if k in ("comments", "work_notes")}
    state = {k: v for k, v in payload.items() if k not in ("comments", "work_notes")}

    if state:
        requests.patch(url, auth=auth, headers=headers, json=state, timeout=30).raise_for_status()
    if journal:
        requests.patch(url, auth=auth, headers=headers, json=journal, timeout=30).raise_for_status()


def build_payload(mode: str) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    project = get_env("REPO_NAME", required=False) or "unknown"
    rg = get_env("RESOURCE_GROUP", required=False) or f"rg-{project}"
    pr_url = get_env("PR_URL", required=False) or ""

    if mode == "success":
        pr_info = f"\nPull Request : {pr_url}" if pr_url else ""
        return {
            "state": "3",  # Closed Complete
            "close_notes": f"Infrastructure provisioned: {rg}",
            "work_notes": (
                f"Azure infrastructure provisioning completed successfully.\n"
                f"Resource Group : {rg}\n"
                f"Completed at   : {stamp}"
                f"{pr_info}"
            ),
            "comments": (
                f"Great news! Your Azure infrastructure has been provisioned successfully.\n\n"
                f"Resource Group : {rg}\n"
                f"{'Pull Request   : ' + pr_url + chr(10) if pr_url else ''}"
                f"\nWhat happens next:\n"
                f"  - A Pull Request has been raised in the azure-infrastructure repository\n"
                f"  - Once the PR is merged, Terraform will apply the infrastructure\n"
                f"  - Your resources will be live within minutes of merge\n\n"
                f"Refer to the Actions tab in GitHub for workflow runs.\n"
                f"Contact us at platformsupport@nexturn.com in case of any issues."
            ),
        }

    if mode == "failed":
        return {
            "state": "2",  # Work in Progress
            "work_notes": (
                f"Azure infrastructure provisioning FAILED.\n"
                f"Target resource group: {rg}\n"
                f"Failed at: {stamp}\n"
                f"Action required: Platform team investigation needed."
            ),
            "comments": (
                "Unfortunately, infrastructure provisioning has failed. "
                "Please check with Platform Team DL: platformsupport@nexturn.com\n\n"
                "The platform team has been notified and will investigate. "
                "You do not need to raise a separate ticket."
            ),
        }

    raise ValueError(f"Unsupported mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update ServiceNow RITM for Azure infra")
    parser.add_argument("--mode", choices=["success", "failed"], required=True)
    args = parser.parse_args()

    base_url = get_env("SNOW_INSTANCE_URL")
    auth = HTTPBasicAuth(get_env("SNOW_USERNAME"), get_env("SNOW_PASSWORD"))
    ritm_number = get_env("RITM_NUMBER", required=False)
    ritm_sys_id = get_env("RITM_SYS_ID", required=False)

    resolved = resolve_ritm_sys_id(base_url, auth, ritm_sys_id, ritm_number)
    payload = build_payload(args.mode)
    patch_ritm(base_url, auth, resolved, payload)
    print(f"Updated RITM {ritm_number or resolved} with mode={args.mode}")


if __name__ == "__main__":
    main()
