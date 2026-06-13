#!/usr/bin/env python3
"""Update ServiceNow RITM for AD Group requests."""

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

    journal = {k: v for k, v in payload.items() if k in ("comments", "work_notes")}
    state = {k: v for k, v in payload.items() if k not in ("comments", "work_notes")}

    if state:
        requests.patch(url, auth=auth, headers=headers, json=state, timeout=30).raise_for_status()
    if journal:
        requests.patch(url, auth=auth, headers=headers, json=journal, timeout=30).raise_for_status()


def build_payload(mode: str) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    request_type = get_env("REQUEST_TYPE", required=False) or "unknown"
    group_name = get_env("GROUP_NAME", required=False) or "unknown"
    user_email = get_env("USER_EMAIL", required=False) or "unknown"

    action = "created and user added" if request_type == "new" else "user added to existing group"

    if mode == "success":
        return {
            "state": "3",  # Closed Complete
            "close_notes": f"AD Group request completed: {group_name}",
            "work_notes": (
                f"AD Group operation completed successfully.\n"
                f"Request Type : {request_type.title()}\n"
                f"Group Name   : {group_name}\n"
                f"User Added   : {user_email}\n"
                f"Completed at : {stamp}"
            ),
            "comments": (
                f"Your AD group request has been completed successfully!\n\n"
                f"Action Performed : {'New group created & member added' if request_type == 'new' else 'Added to existing group'}\n"
                f"Group Name       : {group_name}\n"
                f"User Added       : {user_email}\n"
                f"Completed at     : {stamp}\n\n"
                f"The user now has access to the group in Azure Entra ID.\n"
                f"Contact us at platformsupport@nexturn.com in case of any issues."
            ),
        }

    if mode == "failed":
        return {
            "state": "2",  # Work in Progress
            "work_notes": (
                f"AD Group operation FAILED.\n"
                f"Request Type : {request_type.title()}\n"
                f"Group Name   : {group_name}\n"
                f"User Email   : {user_email}\n"
                f"Failed at    : {stamp}\n"
                f"Action required: Platform team investigation needed."
            ),
            "comments": (
                f"Unfortunately, your AD group request has failed.\n\n"
                f"Group Name : {group_name}\n"
                f"User       : {user_email}\n\n"
                f"The Platform team has been notified and will investigate.\n"
                f"Contact: platformsupport@nexturn.com\n"
                f"You do not need to raise a separate ticket."
            ),
        }

    raise ValueError(f"Unsupported mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update ServiceNow RITM for AD Group")
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
