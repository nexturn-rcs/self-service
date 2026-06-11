module "rg" {
  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//azure/resource-group?ref=develop"

  name     = var.resource_group
  location = var.location
  environment  = var.environment
}

module "aks" {
  count = var.enable_aks ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//azure/aks?ref=develop"

  cluster_name   = "${var.project_name}-${var.environment}-aks"
  resource_group = module.rg.name
  location       = var.location

  environment  = var.environment
  cluster_size = "small"
}

module "storage" {
  count = var.enable_storage ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//azure/storage?ref=develop"

  name                = "${var.project_name}${var.environment}"
  resource_group_name = module.rg.name
  location            = var.location
  environment         = var.environment
}

module "sql" {
  count = var.enable_sql ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//azure/sql?ref=develop"

  server_name   = "${var.project_name}-${var.environment}-sql"
  database_name = "${var.project_name}-db"

  resource_group_name = module.rg.name
  location            = var.location
  environment = var.environment
}

module "kv" {
  count = var.enable_key_vault ? 1 : 0

  source = "git::https://github.com/nexturn-rcs/terraform-modules.git//azure/key-vault?ref=develop"

  name                = "${var.project_name}-${var.environment}-kv"
  resource_group_name = module.rg.name
  location            = var.location
  environment         = var.environment
}

