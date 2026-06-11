terraform {
  backend "azurerm" {
    resource_group_name  = "rg-nextops-otis-tfstate"
    storage_account_name = "nextopsotistfstate"
    container_name       = "tfstate"
    key                  = "${RESOURCE_GROUP}.tfstate"
  }
}
