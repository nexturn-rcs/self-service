#!/usr/bin/env python3
"""
Manage Azure AD Groups via Microsoft Graph API.

Actions:
  - new: Create a new group and add the user as a member
  - existing: Find an existing group and add the user as a member

Required environment variables:
  AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
  REQUEST_TYPE (new/existing), GROUP_NAME, USER_EMAIL
  GROUP_DESCRIPTION (optional, for new groups)
"""

import os
import sys

import msal
import requests


def get_env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        print(f"ERROR: Missing required environment variable: {name}")
        sys.exit(1)
    return value


def get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """Acquire token using MSAL client credentials flow."""
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        print(f"ERROR: Failed to acquire token: {result.get('error_description', result)}")
        sys.exit(1)
    return result["access_token"]


def graph_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def find_group(token: str, group_name: str) -> dict | None:
    """Find a group by display name."""
    resp = requests.get(
        "https://graph.microsoft.com/v1.0/groups",
        headers=graph_headers(token),
        params={"$filter": f"displayName eq '{group_name}'", "$select": "id,displayName"},
        timeout=30,
    )
    resp.raise_for_status()
    groups = resp.json().get("value", [])
    return groups[0] if groups else None


def create_group(token: str, group_name: str, description: str) -> dict:
    """Create a new security group."""
    payload = {
        "displayName": group_name,
        "description": description or f"Created via self-service portal",
        "mailEnabled": False,
        "mailNickname": group_name.replace(" ", "-").lower(),
        "securityEnabled": True,
        "groupTypes": [],
    }
    resp = requests.post(
        "https://graph.microsoft.com/v1.0/groups",
        headers=graph_headers(token),
        json=payload,
        timeout=30,
    )
    if resp.status_code == 400 and "already exists" in resp.text.lower():
        print(f"Group '{group_name}' already exists, finding it...")
        existing = find_group(token, group_name)
        if existing:
            return existing
    resp.raise_for_status()
    group = resp.json()
    print(f"Created group: {group['displayName']} (ID: {group['id']})")
    return group


def find_user(token: str, user_email: str) -> dict:
    """Find user by UPN/email."""
    resp = requests.get(
        f"https://graph.microsoft.com/v1.0/users/{user_email}",
        headers=graph_headers(token),
        params={"$select": "id,displayName,userPrincipalName"},
        timeout=30,
    )
    if resp.status_code == 404:
        print(f"ERROR: User not found: {user_email}")
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def add_member(token: str, group_id: str, user_id: str, user_email: str, group_name: str) -> None:
    """Add user to group."""
    payload = {
        "@odata.id": f"https://graph.microsoft.com/v1.0/directoryObjects/{user_id}"
    }
    resp = requests.post(
        f"https://graph.microsoft.com/v1.0/groups/{group_id}/members/$ref",
        headers=graph_headers(token),
        json=payload,
        timeout=30,
    )
    if resp.status_code == 204:
        print(f"Successfully added {user_email} to group '{group_name}'")
    elif resp.status_code == 400 and "already exist" in resp.text.lower():
        print(f"User {user_email} is already a member of '{group_name}'")
    else:
        resp.raise_for_status()


def main():
    tenant_id = get_env("AZURE_TENANT_ID")
    client_id = get_env("AZURE_CLIENT_ID")
    client_secret = get_env("AZURE_CLIENT_SECRET")
    request_type = get_env("REQUEST_TYPE")
    group_name = get_env("GROUP_NAME")
    group_description = get_env("GROUP_DESCRIPTION", required=False)
    user_email = get_env("USER_EMAIL")

    print(f"Request Type : {request_type}")
    print(f"Group Name   : {group_name}")
    print(f"User Email   : {user_email}")
    print()

    # Authenticate
    print("Authenticating with Azure AD...")
    token = get_access_token(tenant_id, client_id, client_secret)
    print("Authentication successful.\n")

    # Find or create group
    if request_type == "new":
        print(f"Creating new group: {group_name}")
        group = create_group(token, group_name, group_description)
    elif request_type == "existing":
        print(f"Finding existing group: {group_name}")
        group = find_group(token, group_name)
        if not group:
            print(f"ERROR: Group '{group_name}' not found in Azure AD")
            sys.exit(1)
        print(f"Found group: {group['displayName']} (ID: {group['id']})")
    else:
        print(f"ERROR: Invalid request_type: {request_type}")
        sys.exit(1)

    # Find user
    print(f"\nLooking up user: {user_email}")
    user = find_user(token, user_email)
    print(f"Found user: {user['displayName']} ({user['userPrincipalName']})")

    # Add member
    print(f"\nAdding {user_email} to group '{group['displayName']}'...")
    add_member(token, group["id"], user["id"], user_email, group["displayName"])

    print("\n✓ AD Group operation completed successfully.")


if __name__ == "__main__":
    main()
