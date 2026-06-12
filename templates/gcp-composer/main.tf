module "project" {
  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/project?ref=develop"

  project_id   = "${var.project_name}-${var.environment}"
  project_name = var.project_name
  environment  = var.environment
  region       = var.region
}

module "gke" {
  count = var.enable_gke ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/gke?ref=develop"

  cluster_name = "${var.project_name}-${var.environment}-gke"
  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment
  node_count   = 1
}

module "storage" {
  count = var.enable_storage ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/gcs?ref=develop"

  bucket_name = "${var.project_name}-${var.environment}-bucket"
  project_id  = module.project.project_id
  location    = var.region
  environment = var.environment
}

module "sql" {
  count = var.enable_sql ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/cloud-sql?ref=develop"

  instance_name = "${var.project_name}-${var.environment}-sql"
  project_id    = module.project.project_id
  region        = var.region
  environment   = var.environment
}

module "secret_manager" {
  count = var.enable_secret_manager ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//gcp/secret-manager?ref=develop"

  project_id  = module.project.project_id
  environment = var.environment
}
