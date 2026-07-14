#!/usr/bin/env bash
# discover-prometheus.sh — Auto-detect Prometheus in the connected AKS cluster.
#
# Detection order:
#   1. Helm releases — kube-prometheus-stack, standalone prometheus, victoria-metrics
#   2. AKS Managed Prometheus add-on (Azure Monitor)
#   3. kubectl generic service scan (catches any other installation)
#   4. GitHub repository variables fallback (PROMETHEUS_NAMESPACE / PROMETHEUS_SERVICE_NAME)
#   5. Fail with actionable guidance
#
# Usage:
#   bash scripts/discover-prometheus.sh \
#     --resource-group <rg> \
#     --cluster-name   <aks>
#
# Writes GitHub Actions step outputs:
#   PROM_FOUND      true | false
#   PROM_TYPE       port-forward | remote | none
#   PROM_NAMESPACE  k8s namespace  (port-forward only)
#   PROM_SVC        k8s service    (port-forward only)
#   PROM_PORT       service port   (port-forward only)
#   PROM_URL        full URL       (remote only)
#   PROM_SOURCE     how it was discovered

set -euo pipefail

RG=""
AKS_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group) RG="$2";      shift 2 ;;
    --cluster-name)   AKS_NAME="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ── Output helpers ────────────────────────────────────────────────────────────

out() { echo "$1=$2" >> "${GITHUB_OUTPUT:-/dev/null}"; }

found_port_forward() {
  local ns="$1" svc="$2" port="$3" source="$4"
  echo "✅ Prometheus found [$source]"
  echo "   namespace=$ns  service=$svc  port=$port"
  out PROM_FOUND     true
  out PROM_TYPE      port-forward
  out PROM_NAMESPACE "$ns"
  out PROM_SVC       "$svc"
  out PROM_PORT      "$port"
  out PROM_SOURCE    "$source"
  exit 0
}

found_remote() {
  local url="$1" source="$2"
  echo "✅ Remote Prometheus found [$source]"
  echo "   url=$url"
  out PROM_FOUND  true
  out PROM_TYPE   remote
  out PROM_URL    "$url"
  out PROM_SOURCE "$source"
  exit 0
}

not_found() {
  out PROM_FOUND false
  out PROM_TYPE  none
  exit 0
}

# Verify a service actually exists before claiming it
svc_exists() { kubectl get svc "$2" -n "$1" &>/dev/null; }

# ── 1. Helm release discovery ─────────────────────────────────────────────────

if command -v helm &>/dev/null; then
  echo "🔍 Scanning Helm releases..."
  HELM_JSON=$(helm list -A -o json 2>/dev/null || echo "[]")

  parse_release() {
    local pattern="$1"
    python3 -c "
import json, sys, re
releases = json.load(sys.stdin)
for r in releases:
    if re.search(r'$pattern', r.get('chart', '')):
        print(r['name'] + ' ' + r['namespace'])
        break
" 2>/dev/null <<< "$HELM_JSON" || true
  }

  # kube-prometheus-stack  → service: <release>-kube-prometheus-prometheus  port: 9090
  R=$(parse_release "kube-prometheus-stack")
  if [[ -n "$R" ]]; then
    NAME=$(cut -d' ' -f1 <<< "$R"); NS=$(cut -d' ' -f2 <<< "$R")
    SVC="${NAME}-kube-prometheus-prometheus"
    svc_exists "$NS" "$SVC" && found_port_forward "$NS" "$SVC" "9090" "Helm/kube-prometheus-stack"
    # Alternate naming used by some versions
    SVC="${NAME}-prometheus"
    svc_exists "$NS" "$SVC" && found_port_forward "$NS" "$SVC" "9090" "Helm/kube-prometheus-stack"
  fi

  # prometheus (standalone)  → service: <release>-server  port: 80
  R=$(parse_release "^prometheus-[0-9]")
  if [[ -n "$R" ]]; then
    NAME=$(cut -d' ' -f1 <<< "$R"); NS=$(cut -d' ' -f2 <<< "$R")
    SVC="${NAME}-server"
    svc_exists "$NS" "$SVC" && found_port_forward "$NS" "$SVC" "80" "Helm/prometheus"
  fi

  # victoria-metrics-k8s-stack / victoria-metrics-single  → port: 8428
  R=$(parse_release "victoria-metrics")
  if [[ -n "$R" ]]; then
    NAME=$(cut -d' ' -f1 <<< "$R"); NS=$(cut -d' ' -f2 <<< "$R")
    for SVC in \
      "${NAME}-victoria-metrics-single-server" \
      "${NAME}-vmsingle" \
      "vmsingle-${NAME}"; do
      svc_exists "$NS" "$SVC" && found_port_forward "$NS" "$SVC" "8428" "Helm/victoria-metrics"
    done
  fi
fi

# ── 2. AKS Managed Prometheus (Azure Monitor) ─────────────────────────────────

if [[ -n "$RG" && -n "$AKS_NAME" ]] && command -v az &>/dev/null; then
  echo "🔍 Checking AKS Managed Prometheus add-on..."
  MANAGED=$(az aks show \
    --name "$AKS_NAME" --resource-group "$RG" \
    --query "addonProfiles.azureMonitorMetrics.enabled" \
    -o tsv 2>/dev/null || echo "false")

  if [[ "$MANAGED" == "true" ]]; then
    # Try to get the workspace query endpoint from the cluster resource
    QUERY_EP=$(az aks show \
      --name "$AKS_NAME" --resource-group "$RG" \
      --query "azureMonitorProfile.metrics.prometheusQueryEndpoint" \
      -o tsv 2>/dev/null || true)

    if [[ -n "$QUERY_EP" && "$QUERY_EP" != "null" && "$QUERY_EP" != "None" ]]; then
      found_remote "$QUERY_EP" "AKS Managed Prometheus (Azure Monitor)"
    fi

    # AKS managed Prometheus also runs in-cluster components under azuremonitor-metrics
    # Fall through to kubectl scan — it will find them
    echo "  Managed add-on enabled; checking for in-cluster components..."
  fi
fi

# ── 3. kubectl generic service scan ───────────────────────────────────────────

echo "🔍 Scanning all cluster services..."

FOUND=$(kubectl get svc -A -o json 2>/dev/null | python3 -c "
import json, sys

data = json.load(sys.stdin)
PROM_PORTS  = {9090, 80, 8428, 9091}
PROM_NAME_FRAGMENTS = ('prometheus', 'prom', 'victoria', 'vmsingle', 'vmcluster')
PROM_LABELS = {
    'app': 'prometheus',
    'app.kubernetes.io/name': 'prometheus',
    'app.kubernetes.io/name': 'victoria-metrics',
}
SKIP_NS = {'kube-system'}   # skip unless nothing else found

candidates = []
for item in data.get('items', []):
    meta  = item.get('metadata', {})
    spec  = item.get('spec', {})
    name  = meta.get('name', '')
    ns    = meta.get('namespace', '')
    labels = meta.get('labels', {})
    ports  = spec.get('ports', [])

    if spec.get('clusterIP') == 'None':   # headless
        continue

    name_match  = any(f in name.lower() for f in PROM_NAME_FRAGMENTS)
    label_match = any(labels.get(k) == v for k, v in PROM_LABELS.items())
    port_nums   = {p.get('port') for p in ports}
    port_match  = bool(port_nums & PROM_PORTS)

    if (name_match or label_match) and port_match:
        port = next((p for p in (9090, 8428, 80, 9091) if p in port_nums), list(port_nums)[0])
        candidates.append((ns, name, port))

# Score: prefer well-known observability namespaces, deprioritise kube-system
def score(c):
    ns = c[0]
    if ns in ('monitoring', 'prometheus', 'observability', 'azuremonitor-metrics'): return 0
    if ns.startswith('monitor'): return 1
    if ns == 'kube-system': return 3
    return 2

for ns, name, port in sorted(candidates, key=score):
    print(f'{ns} {name} {port}')
    break
" 2>/dev/null || true)

if [[ -n "$FOUND" ]]; then
  NS=$(cut -d' ' -f1 <<< "$FOUND")
  SVC=$(cut -d' ' -f2 <<< "$FOUND")
  PORT=$(cut -d' ' -f3 <<< "$FOUND")
  found_port_forward "$NS" "$SVC" "$PORT" "kubectl service scan"
fi

# ── 4. Repository variables fallback ──────────────────────────────────────────

if [[ -n "${PROMETHEUS_NAMESPACE:-}" && -n "${PROMETHEUS_SERVICE_NAME:-}" ]]; then
  PORT="${PROMETHEUS_PORT:-9090}"
  echo "📋 Using repository variables: $PROMETHEUS_NAMESPACE / $PROMETHEUS_SERVICE_NAME:$PORT"
  found_port_forward \
    "$PROMETHEUS_NAMESPACE" "$PROMETHEUS_SERVICE_NAME" "$PORT" "repository variables"
fi

# ── 5. Not found — print guidance ─────────────────────────────────────────────

cat <<'EOF'
⚠️  Prometheus not found in this cluster.
    Infrastructure metrics will not be collected for this run.

To enable metrics for future runs, choose one option:

  Option A — Install via AKS plugin (recommended):
    Azure plugin → AKS Clusters → [your cluster] → Add-ons → Enable Prometheus

  Option B — Helm (kube-prometheus-stack):
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm install prometheus prometheus-community/kube-prometheus-stack \
      -n monitoring --create-namespace

  Option C — Helm (standalone):
    helm install prometheus prometheus-community/prometheus \
      -n monitoring --create-namespace

  Option D — Set GitHub repository variables:
    PROMETHEUS_NAMESPACE      namespace where Prometheus runs (e.g. monitoring)
    PROMETHEUS_SERVICE_NAME   Kubernetes service name       (e.g. prometheus-server)
    PROMETHEUS_PORT           port (optional, default 9090)

EOF

not_found
