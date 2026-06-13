variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Default GCP region"
  type        = string
  default     = "us-central1"
}

variable "subnet_cidr" {
  description = "CIDR range for the subnet"
  type        = string
  default     = "10.10.0.0/24"
}

variable "enable_gke" {
  description = "Enable GKE cluster provisioning"
  type        = bool
  default     = false
}

variable "gke_node_count" {
  description = "Number of nodes in GKE node pool"
  type        = number
  default     = 1
}

variable "gke_machine_type" {
  description = "Machine type for GKE nodes"
  type        = string
  default     = "e2-medium"
}

variable "enable_storage" {
  description = "Enable Cloud Storage bucket provisioning"
  type        = bool
  default     = false
}

variable "enable_kms" {
  description = "Enable Cloud KMS provisioning"
  type        = bool
  default     = false
}
