terraform {
  backend "gcs" {
    bucket = "nextopsgcpotistfstate"
    prefix = "${PROJECT_NAME}-${ENVIRONMENT}"
  }
}
