"""
Creates an ADO repo + Azure Pipelines CI/CD + scaffolds templates.
ADO counterpart to bootstrap.py.
Auth: SPN via MSAL client-credentials → ADO bearer token.
"""
import base64
import json
import os
import sys

import msal
import requests

sys.path.insert(0, os.path.dirname(__file__))
from template_utils import process_templates


def get_ado_token(client_id, client_secret, tenant_id):
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(
        scopes=["499b84ac-1321-427f-aa17-267ca6975798/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(f"Failed to obtain ADO token: {result.get('error_description')}")
    return result["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_ado_repo(org_url, project, repo_name, token):
    url = f"{org_url}/{project}/_apis/git/repositories?api-version=7.1"
    r = requests.post(url, json={"name": repo_name}, headers=_headers(token))
    if r.status_code == 409:
        print(f"ERROR: Repository '{repo_name}' already exists in project '{project}'.")
        sys.exit(1)
    r.raise_for_status()
    data = r.json()
    print(f"Repository created: {data['remoteUrl']}")
    return data


def commit_templates(org_url, project, repo_id, token, workspace_dir):
    """Initial commit of all scaffolded files to the new repo via ADO Git Push API."""
    changes = []
    for root, _dirs, files in os.walk(workspace_dir):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, workspace_dir).replace("\\", "/")
            with open(full_path, "rb") as f:
                content = base64.b64encode(f.read()).decode()
            changes.append({
                "changeType": "add",
                "item": {"path": f"/{rel_path}"},
                "newContent": {"content": content, "contentType": "base64Encoded"},
            })

    push_url = f"{org_url}/{project}/_apis/git/repositories/{repo_id}/pushes?api-version=7.1"
    payload = {
        "refUpdates": [{"name": "refs/heads/develop", "oldObjectId": "0" * 40}],
        "commits": [{
            "comment": "Initial scaffold via NexTops self-service",
            "changes": changes,
        }],
    }
    r = requests.post(push_url, json=payload, headers=_headers(token))
    r.raise_for_status()
    print(f"Committed {len(changes)} files to 'develop' branch.")


def create_pipeline(org_url, project, repo_id, name, yaml_path, token):
    url = f"{org_url}/{project}/_apis/pipelines?api-version=7.1"
    payload = {
        "name": name,
        "configuration": {
            "type": "yaml",
            "path": yaml_path,
            "repository": {"id": repo_id, "type": "azureReposGit"},
        },
    }
    r = requests.post(url, json=payload, headers=_headers(token))
    r.raise_for_status()
    pipeline_id = r.json()["id"]
    print(f"Pipeline '{name}' created with id={pipeline_id}")
    return pipeline_id


def set_pipeline_variables(org_url, project, pipeline_id, variables, token):
    """Merge secret/plain variables into an existing pipeline definition."""
    get_url = f"{org_url}/{project}/_apis/build/definitions/{pipeline_id}?api-version=7.1"
    r = requests.get(get_url, headers=_headers(token))
    r.raise_for_status()
    defn = r.json()
    defn.setdefault("variables", {})
    for key, spec in variables.items():
        defn["variables"][key] = {
            "value": spec["value"],
            "allowOverride": False,
            "isSecret": spec.get("isSecret", False),
        }
    r = requests.put(get_url, json=defn, headers=_headers(token))
    r.raise_for_status()
    print(f"Variables set on pipeline {pipeline_id}.")


if __name__ == "__main__":
    org_url     = os.environ["ADO_ORG_URL"]
    project     = os.environ["ADO_TARGET_PROJECT"]
    svc         = os.environ["SERVICE_NAME"]
    proj_name   = os.environ["PROJECT_NAME"]
    py_version  = os.environ.get("PYTHON_VERSION", "3.12")
    description = os.environ.get("DESCRIPTION", "Service managed via NexTops self-service")
    acr_name    = os.environ.get("ACR_NAME", "")
    source_dir  = os.environ.get("SOURCE_TEMPLATE_DIR", "templates/python/azuredevops")
    workspace   = "workspace_repo"

    token = get_ado_token(
        os.environ["ADO_CLIENT_ID"],
        os.environ["ADO_CLIENT_SECRET"],
        os.environ["ADO_TENANT_ID"],
    )

    # 1. Scaffold templates locally
    mappings = {
        "${{ values.owner }}":       project,
        "${{ values.repoName }}":    svc,
        "${{ values.projectName }}": proj_name,
        "${{ values.pythonVersion }}": py_version,
        "${{ values.description }}": description,
        "${{ values.acrName }}":     acr_name,
    }
    process_templates(source_dir, workspace, mappings)

    # 2. Create ADO repo
    repo = create_ado_repo(org_url, project, svc, token)
    repo_id = repo["id"]

    # 3. Commit scaffolded files
    commit_templates(org_url, project, repo_id, token, workspace)

    # 4. Create CI and CD pipelines
    ci_id = create_pipeline(org_url, project, repo_id, f"{svc}-ci", "/azure-pipelines.yml", token)
    cd_id = create_pipeline(org_url, project, repo_id, f"{svc}-cd", "/azure-pipelines-deploy.yml", token)

    # 5. Set pipeline variables (ACR + Azure SPN as secrets)
    pipeline_vars = {
        "ACR_NAME":              {"value": acr_name},
        "PROJECT_NAME":          {"value": proj_name},
        "AZURE_CLIENT_ID":       {"value": os.environ.get("AZURE_CLIENT_ID", ""), "isSecret": True},
        "AZURE_CLIENT_SECRET":   {"value": os.environ.get("AZURE_CLIENT_SECRET", ""), "isSecret": True},
        "AZURE_TENANT_ID":       {"value": os.environ.get("AZURE_TENANT_ID", ""), "isSecret": True},
        "AZURE_SUBSCRIPTION_ID": {"value": os.environ.get("AZURE_SUBSCRIPTION_ID", ""), "isSecret": True},
    }
    set_pipeline_variables(org_url, project, ci_id, pipeline_vars, token)
    set_pipeline_variables(org_url, project, cd_id, pipeline_vars, token)

    print(json.dumps({
        "repoUrl": repo.get("remoteUrl"),
        "repoId": repo_id,
        "ciPipelineId": ci_id,
        "cdPipelineId": cd_id,
    }))
