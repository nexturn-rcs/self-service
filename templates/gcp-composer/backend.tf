terraform {
  backend "gcs" {
    bucket = "nextops-tfstate"
    prefix = "${GCP_PROJECT_FOLDER}"
  }
}
