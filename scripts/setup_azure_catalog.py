#!/usr/bin/env python3
"""
ServiceNow Azure Infrastructure Onboarding Catalog Setup
=========================================================
Provisions the following in your ServiceNow instance:

  1. Catalog Category  : "Infrastructure Provisioning"
  2. Catalog Item      : "Azure Infrastructure Onboarding"
  3. Variables         : project_name, environment, location,
                         enable_aks, enable_storage, enable_sql, enable_keyvault
  4. Client Script     : Validates project_name starts with 'nextops'
  5. Business Rule     : Triggers GitHub Actions on RITM approval

Usage:
    python setup_azure_catalog.py \\
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
GITHUB_WORKFLOW = "azure-infrastructure-onboarding.yaml"
GITHUB_BRANCH = "develop"

# ── Catalog variables definition ────────────────────────────────────────────
#   ServiceNow item_option_new types:
#     "6" = Single Line Text
#     "3" = Select Box
#     "7" = Checkbox
CATALOG_VARIABLES = [
    {
        "name": "project_name",
        "question_text": "Project Name",
        "tooltip": (
            "Must start with 'nextops'. "
            "Example: nextops-payments, nextops-data, nextops-platform"
        ),
        "type": "6",
        "mandatory": True,
        "order": 100,
        "default_value": "nextops-",
        "help_text": "Project name must always start with 'nextops'. Used for resource group naming.",
    },
    {
        "name": "environment",
        "question_text": "Environment",
        "tooltip": "Target deployment environment for the infrastructure.",
        "type": "3",
        "mandatory": True,
        "order": 200,
        "default_value": "dev",
        "choices": ["dev", "stage", "prod"],
    },
    {
        "name": "location",
        "question_text": "Azure Region",
        "tooltip": "Azure data center region for resource deployment.",
        "type": "3",
        "mandatory": True,
        "order": 300,
        "default_value": "eastus",
        "choices": ["eastus", "eastus2", "westus", "westus2", "centralus", "northeurope", "westeurope"],
    },
    {
        "name": "enable_aks",
        "question_text": "Enable AKS (Kubernetes)",
        "tooltip": "Provision Azure Kubernetes Service cluster.",
        "type": "7",
        "mandatory": False,
        "order": 400,
        "default_value": "true",
        "help_text": "Creates a managed Kubernetes cluster for container workloads.",
    },
    {
        "name": "enable_storage",
        "question_text": "Enable Storage Account",
        "tooltip": "Provision Azure Storage Account for blob/file storage.",
        "type": "7",
        "mandatory": False,
        "order": 500,
        "default_value": "false",
        "help_text": "Creates a general-purpose v2 storage account.",
    },
    {
        "name": "enable_sql",
        "question_text": "Enable SQL Database",
        "tooltip": "Provision Azure SQL Database instance.",
        "type": "7",
        "mandatory": False,
        "order": 600,
        "default_value": "false",
        "help_text": "Creates a managed SQL database for relational data.",
    },
    {
        "name": "enable_keyvault",
        "question_text": "Enable Key Vault",
        "tooltip": "Provision Azure Key Vault for secrets management.",
        "type": "7",
        "mandatory": False,
        "order": 700,
        "default_value": "true",
        "help_text": "Creates a Key Vault to securely store secrets, keys, and certificates.",
    },
]


class SnowSetup:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

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
            print(f"  Updated  {label}: {existing['sys_id']}")
            return existing["sys_id"]
        created = self._post(table, data)
        print(f"  Created  {label}: {created['sys_id']}")
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
            "title=Infrastructure Provisioning",
            {
                "title": "Infrastructure Provisioning",
                "description": "Request Azure cloud infrastructure resources via platform automation",
                "sc_catalog": catalog_id,
                "active": True,
            },
            "Category 'Infrastructure Provisioning'",
        )

    def create_item(self, category_id: str) -> str:
        return self._upsert(
            "sc_cat_item",
            "name=Azure Infrastructure Onboarding",
            {
                "name": "Azure Infrastructure Onboarding",
                "short_description": (
                    "Provision Azure infrastructure resources — AKS, Storage, SQL, "
                    "Key Vault — via automated Terraform pipelines"
                ),
                "description": (
                    "<h3>Azure Infrastructure Onboarding</h3>"
                    "<p>Submit this request to provision Azure cloud infrastructure "
                    "for your project under the <strong>nexturn-rcs</strong> platform.</p>"
                    "<p>Once approved by the Platform team, automation will:</p>"
                    "<ul>"
                    "<li>Create an Azure Resource Group (<code>rg-{project}-{env}</code>)</li>"
                    "<li>Generate Terraform configurations for selected services</li>"
                    "<li>Raise a Pull Request in the <strong>azure-infrastructure</strong> repository</li>"
                    "<li>Enable selected services: AKS, Storage, SQL, Key Vault</li>"
                    "</ul>"
                    "<p><strong>Naming convention:</strong> Project name must start with "
                    "<code>nextops</code> (e.g., nextops-payments, nextops-data).</p>"
                    "<p><strong>Expected completion time:</strong> 2-3 minutes after approval.</p>"
                    "<p><strong>Support:</strong> platformsupport@nexturn.com</p>"
                ),
                "category": category_id,
                "active": True,
                "visible": True,
                "no_order": False,
                "order": 200,
            },
            "Catalog Item 'Azure Infrastructure Onboarding'",
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
            f"Variable '{var['name']}'",
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
                f"  Choice '{var['name']}={choice}'",
            )

    def create_client_script_validation(self, item_id: str) -> None:
        """Create a Catalog Client Script that validates project_name starts with 'nextops'."""
        script = """
function onChange(control, oldValue, newValue, isLoading) {
    if (isLoading || newValue === '') {
        return;
    }
    if (newValue.indexOf('nextops') !== 0) {
        g_form.showFieldMsg('project_name', 'Project name must start with "nextops" (e.g., nextops-payments)', 'error');
        g_form.setValue('project_name', '');
    } else {
        g_form.hideFieldMsg('project_name');
    }
}
"""
        self._upsert(
            "catalog_script_client",
            f"cat_item={item_id}^variable_name=project_name^name=Validate Project Name Prefix - Azure",
            {
                "cat_item": item_id,
                "name": "Validate Project Name Prefix - Azure",
                "variable_name": "project_name",
                "type": "onChange",
                "script": script,
                "active": True,
                "ui_type": "0",
                "applies_to": "item",
            },
            "Client Script 'Validate Project Name Prefix - Azure'",
        )

    def create_script_include(self) -> None:
        """Ensure GitHubIntegration script include exists (shared with repo onboarding)."""
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

    if (current.cat_item.sys_id.toString() !== '{item_id}') {{
        return;
    }}

    if (current.approval.toString() !== 'approved') {{
        return;
    }}

    if (previous && previous.approval.toString() === 'approved') {{
        return;
    }}

    var projectName  = (current.variables.project_name.getValue() || '').trim();
    var environment  = (current.variables.environment.getValue() || 'dev').trim();
    var location     = (current.variables.location.getValue() || 'eastus').trim();
    var enableAks    = (current.variables.enable_aks.getValue() || 'false').trim();
    var enableStorage = (current.variables.enable_storage.getValue() || 'false').trim();
    var enableSql    = (current.variables.enable_sql.getValue() || 'false').trim();
    var enableKeyvault = (current.variables.enable_keyvault.getValue() || 'false').trim();

    // Validate project name
    if (!projectName || projectName.indexOf('nextops') !== 0) {{
        current.comments = 'Infrastructure provisioning failed validation. Project name must start with "nextops".';
        current.update();
        return;
    }}

    // Mark ticket In Progress
    current.state = 2;
    current.work_notes = 'Azure infrastructure provisioning in progress. Platform automation pipeline triggered for: ' + projectName + '-' + environment;
    current.comments = 'Infrastructure provisioning in progress. Our platform automation is now generating Terraform configurations for your project. You will be notified once the Pull Request is ready.';
    current.update();

    var payload = {{
        event_type: 'servicenow-azure-infra-request',
        client_payload: {{
            project_name: projectName,
            environment: environment,
            location: location,
            enable_aks: enableAks,
            enable_storage: enableStorage,
            enable_sql: enableSql,
            enable_keyvault: enableKeyvault,
            snow_ritm_number: current.number.toString(),
            snow_ritm_sys_id: current.sys_id.toString()
        }}
    }};

    var github = new GitHubIntegration();
    var result = github.triggerRepositoryDispatch(payload);

    if (!result.success) {{
        current.comments = 'Infrastructure provisioning could not be started. Please check with Platform Team DL: platformsupport@nexturn.com';
        current.work_notes = 'GitHub dispatch failed: ' + result.message;
        current.update();
    }}

}})(current, previous);
"""
        self._upsert(
            "sys_script",
            "name=SelfService - Trigger Azure Infra On Approval",
            {
                "name": "SelfService - Trigger Azure Infra On Approval",
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
                "order": 200,
                "description": "On approval, mark in-progress and trigger Azure infra workflow",
            },
            "Business Rule 'Trigger Azure Infra On Approval'",
        )

    def create_approval_rules(self, item_id: str, group_id: str) -> None:
        """Reuse approval enforcement for this catalog item."""
        self._upsert(
            "sys_script",
            "name=SelfService - Require Approval on Azure Infra RITM",
            {
                "name": "SelfService - Require Approval on Azure Infra RITM",
                "collection": "sc_req_item",
                "when": "before",
                "action_insert": True,
                "action_update": False,
                "action_delete": False,
                "action_query": False,
                "active": True,
                "advanced": True,
                "order": 50,
                "description": "Forces approval=requested for Azure infra requests",
                "script": f"""(function executeRule(current, previous) {{
    if (current.cat_item.sys_id.toString() !== '{item_id}') {{ return; }}
    current.approval = 'requested';
}})(current, previous);""",
            },
            "BR: Require Approval on Azure Infra RITM",
        )

        self._upsert(
            "sys_script",
            "name=SelfService - Create Approval for Azure Infra RITM",
            {
                "name": "SelfService - Create Approval for Azure Infra RITM",
                "collection": "sc_req_item",
                "when": "after",
                "action_insert": True,
                "action_update": False,
                "action_delete": False,
                "action_query": False,
                "active": True,
                "advanced": True,
                "order": 60,
                "description": "Creates approval tasks for Platform Approvers on Azure infra requests",
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
            "BR: Create Approval for Azure Infra RITM",
        )

    def setup(self, github_pat: str) -> None:
        print("\n" + "=" * 60)
        print("  ServiceNow Azure Infrastructure Catalog Setup")
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

        print("\n[5/8] Client Script Validation (project_name must start with 'nextops')")
        self.create_client_script_validation(item_id)

        print("\n[6/8] Script Include (GitHubIntegration)")
        self.create_script_include()

        print("\n[7/8] Business Rule (GitHub Trigger on Approval)")
        self.create_business_rule(item_id)

        print("\n[8/8] Approval Group & Rules")
        # Reuse existing Platform Approvers group
        group = self._get("sys_user_group", "name=Platform Approvers")
        if group:
            group_id = group["sys_id"]
            print(f"  Using existing group: {group_id}")
        else:
            group_id = self._upsert(
                "sys_user_group", "name=Platform Approvers",
                {"name": "Platform Approvers", "description": "Approvers for self-service requests", "active": True},
                "Group 'Platform Approvers'",
            )
        self.create_approval_rules(item_id, group_id)

        print("\n" + "=" * 60)
        print("  Setup Complete!")
        print("=" * 60)
        print(f"""
Catalog URL  : {self.base_url}/sp?id=sc_home
Catalog Item : {self.base_url}/sp?id=sc_cat_item&sys_id={item_id}

GitHub Repo  : https://github.com/{GITHUB_ORG}/{GITHUB_REPO}
Workflow     : {GITHUB_WORKFLOW} (branch: {GITHUB_BRANCH})

Note: The project_name field has client-side validation
      enforcing it must start with 'nextops'.
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup ServiceNow catalog for Azure infrastructure onboarding")
    parser.add_argument("--snow-url", required=True)
    parser.add_argument("--snow-user", required=True)
    parser.add_argument("--snow-pass", required=True)
    parser.add_argument("--github-pat", required=True)
    args = parser.parse_args()

    client = SnowSetup(args.snow_url, args.snow_user, args.snow_pass)
    client.setup(args.github_pat)


if __name__ == "__main__":
    main()
