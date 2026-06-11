# ${{ values.repoName }}

## Overview

${{ values.description }}

## Service Information

| Property | Value |
|-----------|---------|
| Repository | ${{ values.repoName }} |
| Project | ${{ values.projectName }} |
| Runtime | Python |
| Deployment | AKS |
| Registry | nextopsacrdemo |

## Endpoints

| Endpoint | Purpose |
|-----------|---------|
| / | Application Home |
| /health | Liveness Probe |
| /ready | Readiness Probe |
| /metrics | Prometheus Metrics |

## CI/CD

This service is deployed automatically through GitHub Actions.
