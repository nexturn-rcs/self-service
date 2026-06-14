locals {
  project_name = "${PROJECT_NAME}"
  environment  = "${ENVIRONMENT}"
  region       = "${REGION}"
  name_prefix  = "${PROJECT_NAME}-${ENVIRONMENT}"
}

# ── Network ─────────────────────────────────────────────────────────────────
module "network" {
  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/network?ref=feature/gcp"

  project_id  = var.project_id
  vpc_name    = "${local.name_prefix}-vpc"
  subnet_name = "${local.name_prefix}-subnet"
  region      = local.region
  subnet_cidr = var.subnet_cidr
}

# ── GKE Cluster ─────────────────────────────────────────────────────────────
module "gke" {
  count  = var.enable_gke ? 1 : 0
  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/gke?ref=feature/gcp"

  project_id   = var.project_id
  cluster_name = "${local.name_prefix}-gke"
  location     = local.region
  node_count   = var.gke_node_count
  machine_type = var.gke_machine_type
  network      = module.network.vpc_name
  subnetwork   = module.network.subnet_name
}

# ── Cloud Storage Bucket ─────────────────────────────────────────────────────
module "storage_bucket" {
  count  = var.enable_storage ? 1 : 0
  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/gcs?ref=feature/gcp"

  project_id    = var.project_id
  bucket_name   = "${local.name_prefix}-bucket"
  location      = upper(local.region)
  storage_class = "STANDARD"
}

# ── Cloud KMS ────────────────────────────────────────────────────────────────
module "kms" {
  count  = var.enable_kms ? 1 : 0
  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/secret-manager?ref=feature/gcp"

  project_id      = var.project_id
  location        = local.region
  key_ring_name   = "${local.name_prefix}-keyring"
  crypto_key_name = "${local.name_prefix}-key"
}
