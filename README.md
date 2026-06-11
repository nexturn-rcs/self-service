# self-service
# Nexturn RCS Self-Service Platform Engineering Hub

Welcome to the central orchestration repository for the internal developer self-service automation engine. This platform handles automated workspace setups, code repositories, and target cloud infrastructure alignments for developers across the organization.

---

## 🚀 Active Capabilities

### 1. Repository Onboarding
* **Workflow File:** `.github/workflows/repository-onboarding.yaml`
* **Purpose:** Automatically provisions a brand-new application repository under the `nexturn-rcs` organization, scaffolds standardized runtime boilerplate from templates, configures operational default branches, and injects required governance configurations.

---

## 🛠️ How the Onboarding Automation Works

When a team member runs the **Repository Onboarding** workflow via the GitHub Actions UI dashboard, the underlying orchestrator executes the following multi-phased pipeline process:

```text
  [ Developer Fills GitHub Form UI ]
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 1. API Provisioning Shell                             │
│    - Sends secure POST request to GitHub API           │
│    - Creates a private repository under nexturn-rcs    │
├────────────────────────────────────────────────────────┤
│ 2. Git Branch Standardization                         │
│    - Initializes empty repository local workspace      │
│    - Upstreams code targeting the 'develop' branch     │
│    - Configures 'develop' as the default main branch   │
├────────────────────────────────────────────────────────┤
│ 3. Template Scaffolding Engine                         │
│    - Normalizes system slash pathing safely for Linux  │
│    - Performs recursive find-and-replace compilation   │
│    - Translates old Backstage macros to runtime inputs │
├────────────────────────────────────────────────────────┤
│ 4. Governance & Parameter Propagation                 │
│    - Injects Repository Variables (e.g. DEPLOY_TARGET) │
│    - Securely binds organization cloud credentials     │
└────────────────────────────────────────────────────────┘
                 │
                 ▼
   [ Automated Clean Architecture Microservice is Live! ]

Workflow Execution Inputs
The workflow UI form collects the following parameters from the developer:

Project Name: The parent application domain group name (e.g., nextops).

Service Name: The direct repository and system identifier (e.g., payment-service).

Python Version: Dropdown runtime selection target (3.11, 3.12, or 3.13).

Service Description: Explicit context detail outlining the microservice's goal.


Repository File Structure

self-service/
├── .github/
│   └── workflows/
│       ├── azure-infrastructure-onboarding.yaml   # Placeholder for Phase 5
│       └── repository-onboarding.yaml            # Phase 3 Orchestration Form
├── templates/
│   └── python/
│       └── skeleton/                             # Core Python boilerplate application
│           ├── .github/workflows/                # Application-level CI/CD pipelines
│           ├── deploy/helm/                      # Kubernetes Helm charts
│           ├── src/                              # FastAPI application logic
│           ├── tests/                            # Automated suite tests
│           ├── Dockerfile                        # Container build template
│           └── requirements.txt                  # Python dependencies
├── bootstrap.py                                  # Core OS-agnostic Python automation execution engine
└── README.md                                     # System documentation hub


Propagated Variables & Secrets

The automation engine automatically sets up the following parameters inside the newly created application repository so it runs out-of-the-box:

Repository Variables
PROJECT_NAME: The structural group label provided by the user.

PYTHON_VER: The targeted runtime selection.

ACR_NAME: The platform enterprise registry (nextopsacrdemo).

DEPLOY_TARGET: Programmatically set to AKS for cloud deployment identification.

Repository Secrets
AZURE_CLIENT_ID: The operational corporate client principal ID.

AZURE_CLIENT_SECRET: Secure encryption authentication token credentials.

AZURE_TENANT_ID: Targeted platform subscriber space group configuration.

AZURE_SUBSCRIPTION_ID: Root resource scope identifier.

🔧 Maintenance & Local Troubleshooting
System Path Normalization
The bootstrap.py engine relies on os.path.normpath() processing rules. This allows developers to edit or test templates locally on Windows using backslashes (\), while guaranteeing the compilation runs flawlessly on the Linux virtual environments (/) used by GitHub Actions.

Secret Rotations
To change the Azure credentials pushed down to new microservices, simply update the Environment Secrets (GLOBAL_AZURE_XYZ) inside the main self-service repository settings panel.