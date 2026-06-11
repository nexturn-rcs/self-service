import json
import os
import shutil
import urllib.request


def create_github_repo(org_name, repo_name, description, token):
    """Sends a POST request to GitHub REST API to provision a new organization repository."""
    url = f"https://api.github.com/orgs/{org_name}/repos"
   
    payload = {
        "name": repo_name,
        "description": description,
        "private": True,
        "has_issues": True,
        "has_projects": False,
        "has_wiki": False
    }
   
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
   
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
   
    try:
        print(f"Sending API request to create repository: {org_name}/{repo_name}...")
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            print(f"Successfully provisioned repository via API: {res_data['html_url']}")
            return res_data['clone_url']
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        if e.code == 422 and "already exists" in error_body:
            print(f"⚠️ Warning: Repository '{repo_name}' already exists. Continuing scaffolding...")
            return f"https://github.com/{org_name}/{repo_name}.git"
        else:
            print(f"❌ Failed to create repository via API. Status Code: {e.code}")
            raise e


def process_templates_and_scaffold(source_dir, target_dir, mappings):
    """Recursively parses template boilerplate, handles file transfers, and replaces tokens."""
    # Standardize path slashes for the hosting OS
    normalized_source = os.path.normpath(source_dir)
    print(f"Starting template search inside normalized path: {normalized_source}")
   
    if not os.path.exists(normalized_source):
        print(f"❌ ERROR: Source template directory '{normalized_source}' does not exist!")
        return

    for root, dirs, files in os.walk(normalized_source):
        relative_path = os.path.relpath(root, normalized_source)
       
        if relative_path == ".":
            dest_root = target_dir
        else:
            dest_root = os.path.join(target_dir, relative_path)
       
        # Ensure target subdirectories exist
        os.makedirs(dest_root, exist_ok=True)

        for file_name in files:
            src_file_path = os.path.join(root, file_name)
            dest_file_path = os.path.join(dest_root, file_name)
           
            print(f"📄 Processing template file: {os.path.join(relative_path, file_name)}")

            try:
                # Open template file and read its content strings safely
                with open(src_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
               
                # Iterate and replace every old Backstage placeholder notation
                for placeholder, live_value in mappings.items():
                    content = content.replace(placeholder, live_value)
               
                # Save out the compiled, translated code file
                with open(dest_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                # Fallback handler for binary/images configuration files
                shutil.copy2(src_file_path, dest_file_path)

    print("🏁 Template generation step completed successfully!")


if __name__ == "__main__":
    GITHUB_TOKEN = os.environ["PLATFORM_AUTOMATION_TOKEN"]
    ORG_NAME = "nexturn-rcs"
    SERVICE_NAME = os.environ["SERVICE_NAME"]
    PROJECT_NAME = os.environ["PROJECT_NAME"]
    PYTHON_VERSION = os.environ["PYTHON_VERSION"]
    DESCRIPTION = os.environ.get("DESCRIPTION", "Service managed via Nexturn RCS automation engine")

    # Step A: Run API request to construct remote cloud repository shell
    clone_url = create_github_repo(ORG_NAME, SERVICE_NAME, DESCRIPTION, GITHUB_TOKEN)

    # Step B: Declare old Backstage token configurations to map out
    template_placeholders = {
        "${{ values.owner }}": ORG_NAME,
        "${{ values.repoName }}": SERVICE_NAME,
        "${{ values.projectName }}": PROJECT_NAME,
        "${{ values.pythonVersion }}": PYTHON_VERSION,
        "${{ values.description }}": DESCRIPTION
    }

    # Step C: Compile files locally into checked-out workspace directory
    process_templates_and_scaffold(
        source_dir="templates/python/skeleton",
        target_dir="workspace_repo",
        mappings=template_placeholders
    )