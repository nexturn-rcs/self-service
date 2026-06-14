project_id  = "${GCP_PROJECT_ID}"
region      = "${REGION}"
subnet_cidr = "10.10.0.0/24"

enable_gke       = "${ENABLE_GKE}"
gke_node_count   = 1
gke_machine_type = "e2-medium"

enable_storage = "${ENABLE_STORAGE}"
enable_kms     = "${ENABLE_KMS}"
