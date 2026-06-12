#!/usr/bin/env python3
"""
ServiceNow AD Group Request Catalog Setup
==========================================
Provisions the following in your ServiceNow instance:

  1. Catalog Category  : "Identity & Access Management"
  2. Catalog Item      : "Azure AD Group Request"
  3. Variables         : request_type, group_name, group_description,
                         user_email, business_justification
  4. Client Script     : Show/hide description based on request type
  5. Business Rule     : Triggers GitHub Actions on RITM approval

Usage:
    python setup_adgroup_catalog.py \\
        --snow-url  "https://dev185439.service-now.com" \\
        --snow-user "admin" \\
        --snow-pass "YOUR_PASSWORD" \\
        --github-pat "ghp_xxxxxxxxxxxx"
"""

import argparse
from typing import Any, Dict

import requests
from requests.auth import HTTPBasicAuth

# ── GitHub configuration ────────────────────────────────────────────────────
GITHUB_ORG = "nexturn-rcs"
GITHUB_REPO = "self-service"
GITHUB_BRANCH = "develop"

# ── Catalog variables definition ────────────────────────────────────────────
CATALOG_VARIABLES = [
    {
        "name": "request_type",
        "question_text": "Request Type",
        "tooltip": "Select whether you need a new group or want to join an existing one.",
        "type": "3",  # Select Box
        "mandatory": True,
        "order": 100,
        "default_value": "existing",
        "choices": ["new", "existing"],
    },
    {
        "name": "group_name",
        "question_text": "Group Name",
        "tooltip": "Name of the Azure AD group (new or existing).",
        "type": "6",  # Single Line Text
        "mandatory": True,
        "order": 200,
        "default_value": "",
        "help_text": "For new groups, provide the desired name. For existing groups, enter the exact group display name.",
    },
    {
        "name": "group_description",
        "question_text": "Group Description",
        "tooltip": "Description for the new group (only required for new groups).",
        "type": "6",  # Single Line Text
        "mandatory": False,
        "order": 300,
        "default_value": "",
        "help_text": "Provide a brief description of the group's purpose. Only required when creating a new group.",
    },
    {
        "name": "user_email",
        "question_text": "User Email (UPN)",
        "tooltip": "Email address of the user to add to the group.",
        "type": "6",  # Single Line Text
        "mandatory": True,
        "order": 400,
        "default_value": "",
        "help_text": "The user principal name (email) of the person to be added to the group.",
    },
    {
        "name": "business_justification",
        "question_text": "Business Justification",
        "tooltip": "Explain why this access is needed.",
        "type": "2",  # Multi Line Text
        "mandatory": True,
        "order": 500,
        "default_value": "",
        "help_text": "Provide a business reason for this group membership request.",
    },
]


class SnowSetup:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _get(self, table: str, query: str) -> Dict[str, Any] | None:
        resp = requests.get(
            f"{self.base_url}/api/now/table/{table}",
            auth=self.auth, headers=self.headers,
            params={"sysparm_query": query, "sysparm_limit": 1},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json().get("result", [])
        return result[0] if result else None

    def _create(self, table: str, payload: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/now/table/{table}",
            auth=self.auth, headers=self.headers, json=payload, timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def _upsert(self, table: str, query: str, payload: dict, label: str) -> str:
        existing = self._get(table, query)
        if existing:
            sys_id = existing["sys_id"]
            requests.patch(
                f"{self.base_url}/api/now/table/{table}/{sys_id}",
                auth=self.auth, headers=self.headers, json=payload, timeout=30,
            ).raise_for_status()
            print(f"  Updated {label}: {sys_id}")
            return sys_id
        else:
            result = self._create(table, payload)
            sys_id = result["sys_id"]
            print(f"  Created  {label}: {sys_id}")
            return sys_id

    # ── Setup steps ─────────────────────────────────────────────────────────

    def get_catalog(self) -> str:
        cat = self._get("sc_catalog", "title=Service Catalog")
        if not cat:
            raise RuntimeError("Service Catalog not found")
        print(f"  Using catalog: {cat['sys_id']}")
        return cat["sys_id"]

    def create_category(self, catalog_id: str) -> str:
        cat_id = self._upsert(
            "sc_category",
            "title=Identity & Access Management",
            {
                "title": "Identity & Access Management",
                "description": "Manage Azure AD groups, user access, and identity provisioning.",
                "sc_catalog": catalog_id,
                "active": True,
            },
            "Category 'Identity & Access Management'",
        )
        return cat_id

    def create_catalog_item(self, catalog_id: str, category_id: str) -> str:
        item_id = self._upsert(
            "sc_cat_item",
            "name=Azure AD Group Request",
            {
                "name": "Azure AD Group Request",
                "short_description": "Request to create a new Azure AD group or add a user to an existing group.",
                "description": (
                    "<p>Use this form to:</p>"
                    "<ul>"
                    "<li><b>Create a new group</b> in Azure Entra ID and add yourself as a member</li>"
                    "<li><b>Join an existing group</b> by providing the group name</li>"
                    "</ul>"
                    "<p>Approval is required from the Platform Approvers team.</p>"
                ),
                "sc_catalogs": catalog_id,
                "category": category_id,
                "active": True,
                "use_sc_layout": True,
            },
            "Catalog Item 'Azure AD Group Request'",
        )
        return item_id

    def create_variables(self, item_id: str) -> dict:
        var_ids = {}
        for var in CATALOG_VARIABLES:
            var_payload = {
                "name": var["name"],
                "cat_item": item_id,
                "question_text": var["question_text"],
                "tooltip": var.get("tooltip", ""),
                "type": var["type"],
                "mandatory": var.get("mandatory", False),
                "order": var["order"],
                "default_value": var.get("default_value", ""),
            }
            if var.get("help_text"):
                var_payload["help_text"] = var["help_text"]

            vid = self._upsert(
                "item_option_new",
                f"name={var['name']}^cat_item={item_id}",
                var_payload,
                f"Variable '{var['name']}'",
            )
            var_ids[var["name"]] = vid

            # Create choices for select box variables
            if var.get("choices"):
                for choice in var["choices"]:
                    self._upsert(
                        "question_choice",
                        f"question={vid}^value={choice}",
                        {
                            "question": vid,
                            "text": choice.replace("_", " ").title(),
                            "value": choice,
                            "order": var["choices"].index(choice) * 100,
                        },
                        f"  Choice '{var['name']}={choice}'",
                    )

        return var_ids

    def create_client_script(self, item_id: str, var_ids: dict) -> None:
        """Client script to show/hide group_description based on request_type."""
        script = f"""
function onChange(control, oldValue, newValue, isLoading) {{
    if (isLoading) return;
    var descField = g_form.getControl('group_description');
    if (newValue === 'new') {{
        g_form.setMandatory('group_description', true);
        g_form.setDisplay('group_description', true);
    }} else {{
        g_form.setMandatory('group_description', false);
        g_form.setDisplay('group_description', false);
        g_form.setValue('group_description', '');
    }}
}}
"""
        self._upsert(
            "catalog_script_client",
            f"name=Toggle Group Description - AD Group^cat_item={item_id}",
            {
                "name": "Toggle Group Description - AD Group",
                "cat_item": item_id,
                "cat_variable": var_ids["request_type"],
                "type": "onChange",
                "script": script,
                "active": True,
                "ui_type": "0",
                "applies_to": "item",
            },
            "Client Script 'Toggle Group Description - AD Group'",
        )

    def create_script_include(self) -> None:
        """Ensure GitHubIntegration script include exists."""
        existing = self._get("sys_script_include", "name=GitHubIntegration")
        if existing:
            print(f"  Exists   Script Include 'GitHubIntegration': {existing['sys_id']}")
        else:
            script = (
                "var GitHubIntegration = Class.create();\n"
                "GitHubIntegration.prototype = {\n"
                "    initialize: function() {\n"
                "        this.githubToken = gs.getProperty('self.service.github.pat.token', '');\n"
                f"        this.org = '{GITHUB_ORG}';\n"
                f"        this.repo = '{GITHUB_REPO}';\n"
                "    },\n"
                "\n"
                "    triggerRepositoryDispatch: function(payload) {\n"
                "        if (!this.githubToken) {\n"
                "            return { success: false, message: 'GitHub PAT token not configured.' };\n"
                "        }\n"
                "        var endpoint = 'https://api.github.com/repos/' + this.org + '/' + this.repo + '/dispatches';\n"
                "        var rm = new sn_ws.RESTMessageV2();\n"
                "        rm.setHttpMethod('POST');\n"
                "        rm.setEndpoint(endpoint);\n"
                "        rm.setRequestHeader('Authorization', 'Bearer ' + this.githubToken);\n"
                "        rm.setRequestHeader('Accept', 'application/vnd.github+json');\n"
                "        rm.setRequestHeader('Content-Type', 'application/json');\n"
                "        rm.setRequestHeader('X-GitHub-Api-Version', '2022-11-28');\n"
                "        rm.setRequestBody(JSON.stringify(payload));\n"
                "        try {\n"
                "            var response = rm.execute();\n"
                "            var statusCode = response.getStatusCode();\n"
                "            if (statusCode === 204) {\n"
                "                return { success: true, message: 'Workflow dispatched successfully.' };\n"
                "            }\n"
                "            return { success: false, message: 'GitHub API returned HTTP ' + statusCode + ': ' + response.getBody() };\n"
                "        } catch (e) {\n"
                "            return { success: false, message: 'Exception: ' + e.message };\n"
                "        }\n"
                "    },\n"
                "    type: 'GitHubIntegration'\n"
                "};\n"
            )
            self._upsert(
                "sys_script_include", "name=GitHubIntegration",
                {"name": "GitHubIntegration", "api_name": "global.GitHubIntegration",
                 "description": "Triggers GitHub repository_dispatch", "active": True,
                 "access": "public", "client_callable": False, "script": script},
                "Script Include 'GitHubIntegration'",
            )

    def create_business_rule(self, item_id: str) -> None:
        rule_script = f"""
(function executeRule(current, previous) {{

    if (current.cat_item.toString() !== '{item_id}') return;

    // Extract variables
    var requestType = current.variables.request_type.toString();
    var groupName = current.variables.group_name.toString();
    var groupDescription = current.variables.group_description.toString();
    var userEmail = current.variables.user_email.toString();
    var justification = current.variables.business_justification.toString();

    // Mark in progress
    current.state = 2;
    current.work_notes = 'AD Group request in progress. Processing: ' + requestType + ' group "' + groupName + '" for user ' + userEmail;
    current.comments = 'Your AD group request is being processed. You will be notified once completed.';
    current.update();

    var payload = {{
        event_type: 'servicenow-adgroup-request',
        client_payload: {{
            request_type: requestType,
            group_name: groupName,
            group_description: groupDescription,
            user_email: userEmail,
            business_justification: justification,
            snow_ritm_number: current.number.toString(),
            snow_ritm_sys_id: current.sys_id.toString()
        }}
    }};

    var github = new GitHubIntegration();
    var result = github.triggerRepositoryDispatch(payload);

    if (!result.success) {{
        current.comments = 'AD group request could not be started. Please contact Platform Team: platformsupport@nexturn.com';
        current.work_notes = 'GitHub dispatch failed: ' + result.message;
        current.update();
    }}

}})(current, previous);
"""
        self._upsert(
            "sys_script",
            "name=SelfService - Trigger AD Group On Approval",
            {
                "name": "SelfService - Trigger AD Group On Approval",
                "collection": "sc_req_item",
                "when": "after",
                "action_insert": True,
                "action_update": True,
                "action_delete": False,
                "action_query": False,
                "filter_condition": "approval=approved",
                "script": rule_script,
                "active": True,
                "advanced": True,
                "order": 300,
                "description": "On approval, trigger AD group workflow via GitHub Actions",
            },
            "Business Rule 'Trigger AD Group On Approval'",
        )

    def create_approval_rules(self, item_id: str) -> None:
        """Create approval rules for the AD Group catalog item."""
        # Get Platform Approvers group
        group = self._get("sys_user_group", "name=Platform Approvers")
        if group:
            group_id = group["sys_id"]
            print(f"  Using existing group: {group_id}")
        else:
            group_id = self._upsert(
                "sys_user_group",
                "name=Platform Approvers",
                {"name": "Platform Approvers", "description": "Approves self-service platform requests"},
                "Group 'Platform Approvers'",
            )

        # Business Rule: Force approval='requested' on insert
        br_script_require = f"""
(function executeRule(current, previous) {{
    if (current.cat_item.toString() === '{item_id}') {{
        current.approval = 'requested';
    }}
}})(current, previous);
"""
        self._upsert(
            "sys_script",
            "name=SelfService - Require Approval on AD Group RITM",
            {
                "name": "SelfService - Require Approval on AD Group RITM",
                "collection": "sc_req_item",
                "when": "before",
                "action_insert": True,
                "action_update": False,
                "action_delete": False,
                "action_query": False,
                "filter_condition": f"cat_item={item_id}",
                "script": br_script_require,
                "active": True,
                "advanced": True,
                "order": 50,
                "description": "Force approval state on AD Group RITM creation",
            },
            "BR: Require Approval on AD Group RITM",
        )

        # Business Rule: Create approval record
        br_script_approval = f"""
(function executeRule(current, previous) {{
    if (current.cat_item.toString() === '{item_id}') {{
        var approver = new GlideRecord('sysapproval_approver');
        approver.initialize();
        approver.sysapproval = current.sys_id;
        approver.approver = '';
        approver.assignment_group = '{group_id}';
        approver.state = 'requested';
        approver.source_table = 'sc_req_item';
        approver.insert();
    }}
}})(current, previous);
"""
        self._upsert(
            "sys_script",
            "name=SelfService - Create Approval for AD Group RITM",
            {
                "name": "SelfService - Create Approval for AD Group RITM",
                "collection": "sc_req_item",
                "when": "after",
                "action_insert": True,
                "action_update": False,
                "action_delete": False,
                "action_query": False,
                "filter_condition": f"cat_item={item_id}",
                "script": br_script_approval,
                "active": True,
                "advanced": True,
                "order": 100,
                "description": "Create group approval record for AD Group RITM",
            },
            "BR: Create Approval for AD Group RITM",
        )

    # ── Main ────────────────────────────────────────────────────────────────

    def run(self, github_pat: str) -> None:
        print("\n" + "=" * 60)
        print("  ServiceNow AD Group Request Catalog Setup")
        print("=" * 60 + "\n")

        # 1. Catalog
        print("[1/7] Service Catalog")
        catalog_id = self.get_catalog()

        # 2. Category
        print("\n[2/7] Catalog Category")
        category_id = self.create_category(catalog_id)

        # 3. Catalog Item
        print("\n[3/7] Catalog Item")
        item_id = self.create_catalog_item(catalog_id, category_id)

        # 4. Variables
        print("\n[4/7] Catalog Variables")
        var_ids = self.create_variables(item_id)

        # 5. Client Script
        print("\n[5/7] Client Script (show/hide description)")
        self.create_client_script(item_id, var_ids)

        # 6. Script Include
        print("\n[6/7] Script Include (GitHubIntegration)")
        self.create_script_include()

        # 7. Business Rule
        print("\n[7/7] Business Rule & Approval Rules")
        self.create_business_rule(item_id)
        self.create_approval_rules(item_id)

        # Set GitHub PAT property
        self._upsert(
            "sys_properties",
            "name=self.service.github.pat.token",
            {"name": "self.service.github.pat.token", "value": github_pat,
             "description": "GitHub PAT for self-service dispatch", "type": "string"},
            "System Property 'self.service.github.pat.token'",
        )

        print("\n" + "=" * 60)
        print("  Setup Complete!")
        print("=" * 60)
        print(f"\nCatalog URL  : {self.base_url}/sp?id=sc_home")
        print(f"Catalog Item : {self.base_url}/sp?id=sc_cat_item&sys_id={item_id}")
        print(f"\nGitHub Repo  : https://github.com/{GITHUB_ORG}/{GITHUB_REPO}")
        print(f"Workflow     : adgroup-onboarding.yaml (branch: {GITHUB_BRANCH})")
        print(f"\nFields:")
        print(f"  - Request Type: New / Existing")
        print(f"  - Group Name")
        print(f"  - Group Description (shown only for new groups)")
        print(f"  - User Email (UPN)")
        print(f"  - Business Justification")


def main():
    parser = argparse.ArgumentParser(description="Setup AD Group Request catalog in ServiceNow")
    parser.add_argument("--snow-url", required=True, help="ServiceNow instance URL")
    parser.add_argument("--snow-user", required=True, help="ServiceNow admin username")
    parser.add_argument("--snow-pass", required=True, help="ServiceNow admin password")
    parser.add_argument("--github-pat", required=True, help="GitHub PAT token")
    args = parser.parse_args()

    setup = SnowSetup(args.snow_url, args.snow_user, args.snow_pass)
    setup.run(args.github_pat)


if __name__ == "__main__":
    main()
