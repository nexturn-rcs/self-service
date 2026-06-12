#!/usr/bin/env python3
"""
ServiceNow GCP Infrastructure Onboarding Catalog Setup
=======================================================
Provisions the following in your ServiceNow instance:

  1. Catalog Category  : "Infrastructure Provisioning"
  2. Catalog Item      : "GCP Infrastructure Onboarding"
  3. Variables         : project_name, environment, region,
                         enable_gke, enable_storage, enable_sql, enable_secret_manager
  4. Client Script     : Validates project_name starts with 'nextops'
  5. Business Rule     : Triggers GitHub Actions on RITM approval

Usage:
    python setup_gcp_catalog.py \\
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
        "name": "project_name",
        "question_text": "Project Name",
        "tooltip": "Must start with 'nextops'. Example: nextops-data, nextops-platform",
        "type": "6",
        "mandatory": True,
        "order": 100,
        "default_value": "nextops-",
        "help_text": "Project name must always start with 'nextops'. Used for GCP project naming.",
    },
    {
        "name": "environment",
        "question_text": "Environment",
        "tooltip": "Target deployment environment.",
        "type": "3",
        "mandatory": True,
        "order": 200,
        "default_value": "dev",
        "choices": ["dev", "stage", "prod"],
    },
    {
        "name": "region",
        "question_text": "GCP Region",
        "tooltip": "Google Cloud region for resource deployment.",
        "type": "3",
        "mandatory": True,
        "order": 300,
        "default_value": "us-central1",
        "choices": [
            "us-central1", "us-east1", "us-east4", "us-west1", "us-west2",
            "europe-west1", "europe-west2", "europe-west3",
            "asia-east1", "asia-southeast1",
        ],
    },
    {
        "name": "enable_gke",
        "question_text": "Enable GKE (Kubernetes)",
        "tooltip": "Provision Google Kubernetes Engine cluster.",
        "type": "7",
        "mandatory": False,
        "order": 400,
        "default_value": "true",
        "help_text": "Creates a managed Kubernetes cluster for container workloads.",
    },
    {
        "name": "enable_storage",
        "question_text": "Enable Cloud Storage (GCS)",
        "tooltip": "Provision a Google Cloud Storage bucket.",
        "type": "7",
        "mandatory": False,
        "order": 500,
        "default_value": "false",
        "help_text": "Creates a GCS bucket for object/blob storage.",
    },
    {
        "name": "enable_sql",
        "question_text": "Enable Cloud SQL",
        "tooltip": "Provision a Cloud SQL (PostgreSQL) instance.",
        "type": "7",
        "mandatory": False,
        "order": 600,
        "default_value": "false",
        "help_text": "Creates a managed Cloud SQL instance for relational data.",
    },
    {
        "name": "enable_secret_manager",
        "question_text": "Enable Secret Manager",
        "tooltip": "Provision GCP Secret Manager for secrets storage.",
        "type": "7",
        "mandatory": False,
        "order": 700,
        "default_value": "true",
        "help_text": "Enables GCP Secret Manager to securely store API keys, passwords, and certificates.",
    },
]


class SnowSetup:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

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
            print(f"  Updated  {label}: {sys_id}")
            return sys_id
        else:
            result = self._create(table, payload)
            sys_id = result["sys_id"]
            print(f"  Created  {label}: {sys_id}")
            return sys_id

    def get_catalog(self) -> str:
        cat = self._get("sc_catalog", "title=Service Catalog")
        if not cat:
            raise RuntimeError("Service Catalog not found")
        print(f"  Using catalog: {cat['sys_id']}")
        return cat["sys_id"]

    def create_category(self, catalog_id: str) -> str:
        return self._upsert(
            "sc_category",
            "title=Infrastructure Provisioning",
            {
                "title": "Infrastructure Provisioning",
                "description": "Provision cloud infrastructure on Azure and GCP.",
                "sc_catalog": catalog_id,
                "active": True,
            },
            "Category 'Infrastructure Provisioning'",
        )

    def create_catalog_item(self, catalog_id: str, category_id: str) -> str:
        return self._upsert(
            "sc_cat_item",
            "name=GCP Infrastructure Onboarding",
            {
                "name": "GCP Infrastructure Onboarding",
                "short_description": "Provision a new GCP project with infrastructure components (GKE, Storage, SQL, Secret Manager).",
                "description": (
                    "<p>Use this form to provision GCP infrastructure for your project.</p>"
                    "<p>A Pull Request will be raised in the <b>gcp-infrastructure</b> repository. "
                    "Once approved and merged by the Infrastructure team, Terraform will apply your resources.</p>"
                    "<p><b>Note:</b> Project name must start with <b>nextops</b>.</p>"
                ),
                "sc_catalogs": catalog_id,
                "category": category_id,
                "active": True,
                "use_sc_layout": True,
            },
            "Catalog Item 'GCP Infrastructure Onboarding'",
        )

    def create_variables(self, item_id: str) -> None:
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

            if var.get("choices"):
                for choice in var["choices"]:
                    self._upsert(
                        "question_choice",
                        f"question={vid}^value={choice}",
                        {
                            "question": vid,
                            "text": choice,
                            "value": choice,
                            "order": var["choices"].index(choice) * 100,
                        },
                        f"  Choice '{var['name']}={choice}'",
                    )

    def create_client_script(self, item_id: str) -> None:
        """Validate project_name starts with 'nextops'."""
        script = """
function onChange(control, oldValue, newValue, isLoading) {
    if (isLoading) return;
    if (!newValue) return;
    if (newValue.toLowerCase().indexOf('nextops') !== 0) {
        g_form.showFieldMsg('project_name', "Project name must start with 'nextops' (e.g. nextops-data, nextops-platform)", 'error');
        g_form.setValue('project_name', oldValue);
    } else {
        g_form.hideFieldMsg('project_name', true);
    }
}
"""
        self._upsert(
            "catalog_script_client",
            f"name=Validate Project Name Prefix - GCP^cat_item={item_id}",
            {
                "name": "Validate Project Name Prefix - GCP",
                "cat_item": item_id,
                "type": "onChange",
                "script": script,
                "active": True,
                "ui_type": "0",
                "applies_to": "item",
            },
            "Client Script 'Validate Project Name Prefix - GCP'",
        )

    def create_script_include(self) -> None:
        existing = self._get("sys_script_include", "name=GitHubIntegration")
        if existing:
            print(f"  Exists   Script Include 'GitHubIntegration': {existing['sys_id']}")
        else:
            print("  Script Include 'GitHubIntegration' not found — run setup_azure_catalog.py first.")

    def create_business_rule(self, item_id: str) -> None:
        rule_script = f"""
(function executeRule(current, previous) {{

    if (current.cat_item.toString() !== '{item_id}') return;

    var projectName     = current.variables.project_name.toString();
    var environment     = current.variables.environment.toString();
    var region          = current.variables.region.toString();
    var enableGke       = current.variables.enable_gke.toString();
    var enableStorage   = current.variables.enable_storage.toString();
    var enableSql       = current.variables.enable_sql.toString();
    var enableSecretMgr = current.variables.enable_secret_manager.toString();

    if (projectName.toLowerCase().indexOf('nextops') !== 0) {{
        current.comments = 'ERROR: Project name must start with nextops. Request rejected.';
        current.state = 4;
        current.update();
        return;
    }}

    current.state = 2;
    current.work_notes = 'GCP infrastructure provisioning in progress for project: ' + projectName + '-' + environment;
    current.comments = 'GCP infrastructure provisioning in progress. Our platform automation is generating Terraform configurations for your project.';
    current.update();

    var payload = {{
        event_type: 'servicenow-gcp-infra-request',
        client_payload: {{
            project_name:          projectName,
            environment:           environment,
            region:                region,
            enable_gke:            enableGke,
            enable_storage:        enableStorage,
            enable_sql:            enableSql,
            enable_secret_manager: enableSecretMgr,
            snow_ritm_number:      current.number.toString(),
            snow_ritm_sys_id:      current.sys_id.toString()
        }}
    }};

    var github = new GitHubIntegration();
    var result = github.triggerRepositoryDispatch(payload);

    if (!result.success) {{
        current.comments = 'GCP infrastructure provisioning could not be started. Please contact Platform Team: platformsupport@nexturn.com';
        current.work_notes = 'GitHub dispatch failed: ' + result.message;
        current.update();
    }}

}})(current, previous);
"""
        self._upsert(
            "sys_script",
            "name=SelfService - Trigger GCP Infra On Approval",
            {
                "name": "SelfService - Trigger GCP Infra On Approval",
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
                "description": "On approval, trigger GCP infra workflow via GitHub Actions",
            },
            "Business Rule 'Trigger GCP Infra On Approval'",
        )

    def create_approval_rules(self, item_id: str) -> None:
        group = self._get("sys_user_group", "name=Platform Approvers")
        group_id = group["sys_id"] if group else None
        if group_id:
            print(f"  Using existing group: {group_id}")
        else:
            raise RuntimeError("Platform Approvers group not found. Run setup_azure_catalog.py first.")

        br_script_require = f"""
(function executeRule(current, previous) {{
    if (current.cat_item.toString() === '{item_id}') {{
        current.approval = 'requested';
    }}
}})(current, previous);
"""
        self._upsert(
            "sys_script",
            "name=SelfService - Require Approval on GCP Infra RITM",
            {
                "name": "SelfService - Require Approval on GCP Infra RITM",
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
                "description": "Force approval state on GCP Infra RITM creation",
            },
            "BR: Require Approval on GCP Infra RITM",
        )

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
            "name=SelfService - Create Approval for GCP Infra RITM",
            {
                "name": "SelfService - Create Approval for GCP Infra RITM",
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
                "description": "Create group approval record for GCP Infra RITM",
            },
            "BR: Create Approval for GCP Infra RITM",
        )

    def run(self, github_pat: str) -> None:
        print("\n" + "=" * 60)
        print("  ServiceNow GCP Infrastructure Catalog Setup")
        print("=" * 60 + "\n")

        print("[1/8] Service Catalog")
        catalog_id = self.get_catalog()

        print("\n[2/8] Catalog Category")
        category_id = self.create_category(catalog_id)

        print("\n[3/8] Catalog Item")
        item_id = self.create_catalog_item(catalog_id, category_id)

        print("\n[4/8] Catalog Variables")
        self.create_variables(item_id)

        print("\n[5/8] Client Script Validation (project_name must start with 'nextops')")
        self.create_client_script(item_id)

        print("\n[6/8] Script Include (GitHubIntegration)")
        self.create_script_include()

        print("\n[7/8] Business Rule (GitHub Trigger on Approval)")
        self.create_business_rule(item_id)

        print("\n[8/8] Approval Group & Rules")
        self.create_approval_rules(item_id)

        print("\n" + "=" * 60)
        print("  Setup Complete!")
        print("=" * 60)
        print(f"\nCatalog URL  : {self.base_url}/sp?id=sc_home")
        print(f"Catalog Item : {self.base_url}/sp?id=sc_cat_item&sys_id={item_id}")
        print(f"\nGitHub Repo  : https://github.com/{GITHUB_ORG}/{GITHUB_REPO}")
        print(f"Workflow     : gcp-infrastructure-onboarding.yaml (branch: {GITHUB_BRANCH})")
        print(f"\nNote: The project_name field has client-side validation")
        print(f"      enforcing it must start with 'nextops'")


def main():
    parser = argparse.ArgumentParser(description="Setup GCP Infra catalog in ServiceNow")
    parser.add_argument("--snow-url", required=True)
    parser.add_argument("--snow-user", required=True)
    parser.add_argument("--snow-pass", required=True)
    parser.add_argument("--github-pat", required=True)
    args = parser.parse_args()

    setup = SnowSetup(args.snow_url, args.snow_user, args.snow_pass)
    setup.run(args.github_pat)


if __name__ == "__main__":
    main()
