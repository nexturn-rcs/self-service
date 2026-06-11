#!/usr/bin/env python3
"""
ServiceNow Self-Service Repository Onboarding Catalog Setup
============================================================
Provisions the following in your ServiceNow instance:

  1. Catalog Category  : "Repository Provisioning"
  2. Catalog Item      : "New Repository Onboarding Request"
  3. Variables         : project_name, service_name, python_version,
                         service_description, team_name, business_justification
  4. System Property   : self.service.github.pat.token
  5. Script Include    : GitHubIntegration
  6. Business Rule     : Triggers GitHub Actions on RITM approval
  7. Approval Rules    : Forces approval workflow (not auto-approve)

Usage:
    python setup_servicenow_catalog.py \\
        --snow-url  "https://dev185439.service-now.com" \\
        --snow-user "admin" \\
        --snow-pass "YOUR_PASSWORD" \\
        --github-pat "ghp_xxxxxxxxxxxx"
"""

import argparse
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth

# ── GitHub configuration ────────────────────────────────────────────────────
GITHUB_ORG = "nexturn-rcs"
GITHUB_REPO = "self-service"
GITHUB_WORKFLOW = "repository-onboarding.yaml"
GITHUB_BRANCH = "develop"

# ── Catalog variables definition ────────────────────────────────────────────
#   ServiceNow item_option_new types:
#     "6" = Single Line Text
#     "2" = Multi Line Text
#     "3" = Select Box
CATALOG_VARIABLES = [
    {
        "name": "project_name",
        "question_text": "Project Name",
        "tooltip": (
            "The parent application domain or product group name. "
            "Example: nextops, fintech-platform, data-hub"
        ),
        "type": "6",
        "mandatory": True,
        "order": 100,
        "default_value": "",
        "help_text": "Used to group related services under a single project umbrella.",
    },
    {
        "name": "service_name",
        "question_text": "Service / Repository Name",
        "tooltip": (
            "Lowercase letters, numbers and hyphens only (2-40 chars). "
            "This becomes the GitHub repository name. "
            "Example: payment-service, user-api, order-processor"
        ),
        "type": "6",
        "mandatory": True,
        "order": 200,
        "default_value": "",
        "help_text": "Must be unique within nexturn-rcs organization. Also used as container image name.",
    },
    {
        "name": "python_version",
        "question_text": "Python Version",
        "tooltip": "Select the Python runtime version for your application.",
        "type": "3",
        "mandatory": True,
        "order": 300,
        "default_value": "3.12",
        "choices": ["3.11", "3.12", "3.13"],
    },
    {
        "name": "description",
        "question_text": "Service Description",
        "tooltip": "What does this microservice do? Provide a brief functional description.",
        "type": "2",
        "mandatory": True,
        "order": 400,
        "default_value": "",
        "help_text": "Will appear in the repository description on GitHub. Keep it concise and meaningful.",
    },
    {
        "name": "team_name",
        "question_text": "Team / Squad Name",
        "tooltip": "Name of the team or squad that will own and maintain this service.",
        "type": "6",
        "mandatory": True,
        "order": 500,
        "default_value": "",
        "help_text": "Used for repository ownership tagging and CODEOWNERS configuration.",
    },
    {
        "name": "business_justification",
        "question_text": "Business Justification",
        "tooltip": "Why is this new repository needed? What business problem does it solve?",
        "type": "2",
        "mandatory": False,
        "order": 600,
        "default_value": "",
        "help_text": "Helps approvers understand the business context for this request.",
    },
]


class SnowSetup:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Content-Type": "application/json",
                        "Accept": "application/json"}

    def _get(self, table: str, query: str, limit: int = 1):
        resp = requests.get(
            f"{self.base_url}/api/now/table/{table}",
            auth=self.auth,
            headers=self.headers,
            params={"sysparm_query": query, "sysparm_limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json().get("result", [])
        if limit == 1:
            return result[0] if result else None
        return result

    def _post(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/api/now/table/{table}",
            auth=self.auth,
            headers=self.headers,
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def _patch(self, table: str, sys_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.patch(
            f"{self.base_url}/api/now/table/{table}/{sys_id}",
            auth=self.auth,
            headers=self.headers,
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def _upsert(self, table: str, query: str, data: Dict[str, Any], label: str) -> str:
        existing = self._get(table, query)
        if existing:
            self._patch(table, existing["sys_id"], data)
            print(f"Updated  {label}: {existing['sys_id']}")
            return existing["sys_id"]
        created = self._post(table, data)
        print(f"Created  {label}: {created['sys_id']}")
        return created["sys_id"]

    def get_catalog(self) -> str:
        catalog = self._get("sc_catalog", "title=Service Catalog^active=true")
        if catalog:
            return catalog["sys_id"]
        fallback = self._get("sc_catalog", "active=true")
        if fallback:
            return fallback["sys_id"]
        raise RuntimeError("No active Service Catalog found")

    def create_category(self, catalog_id: str) -> str:
        return self._upsert(
            "sc_category",
            "title=Repository Provisioning",
            {
                "title": "Repository Provisioning",
                "description": "Request creation of a new application repository",
                "sc_catalog": catalog_id,
                "active": True,
            },
            "Category",
        )

    def create_item(self, category_id: str) -> str:
        return self._upsert(
            "sc_cat_item",
            "name=New Repository Onboarding Request",
            {
                "name": "New Repository Onboarding Request",
                "short_description": (
                    "Request a new GitHub repository with production-ready "
                    "starter code, Dockerization, Helm charts, and CI/CD pipelines"
                ),
                "description": (
                    "<h3>Repository Onboarding Request</h3>"
                    "<p>Submit this request to provision a new application repository "
                    "under the <strong>nexturn-rcs</strong> GitHub organization.</p>"
                    "<p>Once approved by the Platform team, automation will:</p>"
                    "<ul>"
                    "<li>Create a private GitHub repository</li>"
                    "<li>Scaffold production-ready Python starter code (FastAPI)</li>"
                    "<li>Enable Dockerization</li>"
                    "<li>Include unit test scaffolding</li>"
                    "<li>Configure Helm chart for AKS deployment</li>"
                    "<li>Set up CI/CD pipeline workflows</li>"
                    "<li>Inject Azure cloud credentials and configuration</li>"
                    "</ul>"
                    "<p><strong>Expected completion time:</strong> 2-5 minutes after approval.</p>"
                    "<p><strong>Support:</strong> platformsupport@nexturn.com</p>"
                ),
                "category": category_id,
                "active": True,
                "visible": True,
                "no_order": False,
                "order": 100,
            },
            "Catalog Item",
        )

    def create_variable(self, item_id: str, var: Dict[str, Any]) -> None:
        var_id = self._upsert(
            "item_option_new",
            f"cat_item={item_id}^name={var['name']}",
            {
                "cat_item": item_id,
                "name": var["name"],
                "question_text": var["question_text"],
                "tooltip": var.get("tooltip", ""),
                "type": var["type"],
                "mandatory": var.get("mandatory", False),
                "order": var.get("order", 100),
                "default_value": var.get("default_value", ""),
                "help_text": var.get("help_text", ""),
                "active": True,
            },
            f"Variable {var['name']}",
        )

        for i, choice in enumerate(var.get("choices", []), start=1):
            self._upsert(
                "question_choice",
                f"question={var_id}^value={choice}",
                {
                    "question": var_id,
                    "text": choice,
                    "value": choice,
                    "order": i * 100,
                },
                f"Choice {var['name']}={choice}",
            )

    def create_github_pat_property(self, pat: str) -> None:
        self._upsert(
            "sys_properties",
            "name=self.service.github.pat.token",
            {
                "name": "self.service.github.pat.token",
                "value": pat,
                "type": "string",
                "description": "PAT used by ServiceNow to trigger repository_dispatch",
                "read_roles": "admin",
                "write_roles": "admin",
            },
            "System Property self.service.github.pat.token",
        )

    def create_script_include(self) -> None:
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
            "\n"
            "        var endpoint = 'https://api.github.com/repos/' + this.org + '/' + this.repo + '/dispatches';\n"
            "        var rm = new sn_ws.RESTMessageV2();\n"
            "        rm.setHttpMethod('POST');\n"
            "        rm.setEndpoint(endpoint);\n"
            "        rm.setRequestHeader('Authorization', 'Bearer ' + this.githubToken);\n"
            "        rm.setRequestHeader('Accept', 'application/vnd.github+json');\n"
            "        rm.setRequestHeader('Content-Type', 'application/json');\n"
            "        rm.setRequestHeader('X-GitHub-Api-Version', '2022-11-28');\n"
            "        rm.setRequestBody(JSON.stringify(payload));\n"
            "\n"
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
            "\n"
            "    type: 'GitHubIntegration'\n"
            "};\n"
        )

        self._upsert(
            "sys_script_include",
            "name=GitHubIntegration",
            {
                "name": "GitHubIntegration",
                "api_name": "global.GitHubIntegration",
                "description": "Triggers GitHub repository_dispatch for repo onboarding",
                "active": True,
                "access": "public",
                "client_callable": False,
                "script": script,
            },
            "Script Include GitHubIntegration",
        )

    def create_business_rule(self, item_id: str) -> None:
        rule_script = f"""
(function executeRule(current, previous) {{

    if (current.cat_item.sys_id.toString() !== '{item_id}') {{
        return;
    }}

    if (current.approval.toString() !== 'approved') {{
        return;
    }}

    if (previous && previous.approval.toString() === 'approved') {{
        return;
    }}

    var projectName   = (current.variables.project_name.getValue() || '').trim();
    var serviceName   = (current.variables.service_name.getValue() || '').trim();
    var pythonVersion = (current.variables.python_version.getValue() || '3.12').trim();
    var description   = (current.variables.description.getValue() || 'Microservice managed via Nexturn RCS automation').trim();
    var teamName      = (current.variables.team_name.getValue() || '').trim();

    if (!serviceName || !/^[a-z0-9][a-z0-9-]{{1,38}}[a-z0-9]$|^[a-z0-9]$/.test(serviceName)) {{
        current.comments = 'Repository creation failed validation. Service name must be lowercase letters, numbers and hyphens only (2-40 chars).';
        current.update();
        return;
    }}

    // Mark ticket In Progress with informative comment
    current.state = 2;
    current.work_notes = 'Repository creation in progress. Platform automation pipeline triggered for: ' + serviceName;
    current.comments = 'Repository creation in progress. Our platform automation is now building your repository (' + serviceName + '). You will be notified once it is ready.';
    current.update();

    var payload = {{
        event_type: 'servicenow-repo-request',
        client_payload: {{
            project_name: projectName,
            service_name: serviceName,
            python_version: pythonVersion,
            description: description,
            team_name: teamName,
            snow_ritm_number: current.number.toString(),
            snow_ritm_sys_id: current.sys_id.toString()
        }}
    }};

    var github = new GitHubIntegration();
    var result = github.triggerRepositoryDispatch(payload);

    if (!result.success) {{
        current.comments = 'Repository creation could not be started. Please check with Platform Team DL: platformsupport@nexturn.com';
        current.work_notes = 'GitHub dispatch failed: ' + result.message;
        current.update();
    }}

}})(current, previous);
"""

        self._upsert(
            "sys_script",
            "name=SelfService - Trigger Repo Onboarding On Approval",
            {
                "name": "SelfService - Trigger Repo Onboarding On Approval",
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
                "order": 100,
                "description": "On approval, mark in-progress and trigger GitHub onboarding workflow",
            },
            "Business Rule Trigger Repo Onboarding",
        )

    def create_approval_group(self) -> str:
        """Create 'Platform Approvers' group for RITM approval routing."""
        return self._upsert(
            "sys_user_group",
            "name=Platform Approvers",
            {
                "name": "Platform Approvers",
                "description": "Approvers for self-service repository onboarding requests",
                "active": True,
            },
            "Group 'Platform Approvers'",
        )

    def create_approval_rules(self, item_id: str, group_id: str) -> None:
        """Create business rules to enforce approval workflow."""

        # BR: BEFORE INSERT — force approval = requested (blocks auto-approve for admin)
        self._upsert(
            "sys_script",
            "name=SelfService - Require Approval on RITM Create",
            {
                "name": "SelfService - Require Approval on RITM Create",
                "collection": "sc_req_item",
                "when": "before",
                "action_insert": True,
                "action_update": False,
                "action_delete": False,
                "action_query": False,
                "active": True,
                "advanced": True,
                "order": 50,
                "description": "Forces approval=requested for repo onboarding requests",
                "script": f"""(function executeRule(current, previous) {{
    if (current.cat_item.sys_id.toString() !== '{item_id}') {{ return; }}
    current.approval = 'requested';
}})(current, previous);""",
            },
            "BR: Require Approval on RITM Create",
        )

        # BR: AFTER INSERT — create sysapproval_approver records
        self._upsert(
            "sys_script",
            "name=SelfService - Create Approval Records on RITM Insert",
            {
                "name": "SelfService - Create Approval Records on RITM Insert",
                "collection": "sc_req_item",
                "when": "after",
                "action_insert": True,
                "action_update": False,
                "action_delete": False,
                "action_query": False,
                "active": True,
                "advanced": True,
                "order": 60,
                "description": "Creates approval tasks for Platform Approvers on repo requests",
                "script": f"""(function executeRule(current, previous) {{
    if (current.cat_item.sys_id.toString() !== '{item_id}') {{ return; }}

    var gm = new GlideRecord('sys_user_grmember');
    gm.addQuery('group', '{group_id}');
    gm.query();

    while (gm.next()) {{
        var appr = new GlideRecord('sysapproval_approver');
        appr.setValue('source_table', 'sc_req_item');
        appr.setValue('document_id',  current.sys_id);
        appr.setValue('approver',     gm.getValue('user'));
        appr.setValue('state',        'requested');
        appr.setValue('group',        '{group_id}');
        appr.insert();
    }}
}})(current, previous);""",
            },
            "BR: Create Approval Records on RITM Insert",
        )

    def setup(self, github_pat: str) -> None:
        print("\n" + "=" * 60)
        print("  ServiceNow Repository Onboarding Catalog Setup")
        print("=" * 60 + "\n")

        print("[1/8] Service Catalog")
        catalog_id = self.get_catalog()
        print(f"  Using catalog: {catalog_id}")

        print("\n[2/8] Catalog Category")
        category_id = self.create_category(catalog_id)

        print("\n[3/8] Catalog Item")
        item_id = self.create_item(category_id)

        print("\n[4/8] Catalog Variables")
        for var in CATALOG_VARIABLES:
            self.create_variable(item_id, var)

        print("\n[5/8] GitHub PAT System Property")
        self.create_github_pat_property(github_pat)

        print("\n[6/8] Script Include (GitHubIntegration)")
        self.create_script_include()

        print("\n[7/8] Business Rule (GitHub Trigger on Approval)")
        self.create_business_rule(item_id)

        print("\n[8/8] Approval Group & Rules")
        group_id = self.create_approval_group()
        self.create_approval_rules(item_id, group_id)

        # ── Summary ───────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  Setup Complete!")
        print("=" * 60)
        print(f"""
Catalog URL  : {self.base_url}/sp?id=sc_home
Catalog Item : {self.base_url}/sp?id=sc_cat_item&sys_id={item_id}
Admin View   : {self.base_url}/sc?id=sc_cat_item&sys_id={item_id}

GitHub Repo  : https://github.com/{GITHUB_ORG}/{GITHUB_REPO}
Workflow     : {GITHUB_WORKFLOW} (branch: {GITHUB_BRANCH})

Next Steps:
  1. Add members to 'Platform Approvers' group in ServiceNow
     {self.base_url}/sys_user_group.do?sys_id={group_id}

  2. Add secrets to GitHub repo:
     https://github.com/{GITHUB_ORG}/{GITHUB_REPO}/settings/secrets/actions
     - SNOW_INSTANCE_URL  = {self.base_url}
     - SNOW_USERNAME      = admin
     - SNOW_PASSWORD      = (your admin password)
     - PLATFORM_AUTOMATION_TOKEN = (GitHub PAT with repo+workflow scope)

  3. Test: submit a request, approve it, watch GitHub Actions run.
""")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Setup ServiceNow catalog for repo onboarding")
    parser.add_argument("--snow-url", required=True)
    parser.add_argument("--snow-user", required=True)
    parser.add_argument("--snow-pass", required=True)
    parser.add_argument("--github-pat", required=True)
    args = parser.parse_args()

    client = SnowSetup(args.snow_url, args.snow_user, args.snow_pass)
    client.setup(args.github_pat)


if __name__ == "__main__":
    main()
