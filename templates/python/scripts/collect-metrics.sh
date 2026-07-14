#!/usr/bin/env bash
# collect-metrics.sh — generate nextops-metrics/v1 JSON from Prometheus + JTL
#
# Usage:
#   ./scripts/collect-metrics.sh \
#     --jtl results/results.jtl \
#     --start 2026-07-14T10:00:00Z \
#     --end   2026-07-14T10:05:00Z \
#     --output metrics-results/metrics-results.json
#
# Env vars (set by perf-test.yml before calling this script):
#   PROMETHEUS_URL     Prometheus base URL (http://localhost:9090 after port-forward)
#   SERVICE_NAMESPACE  Kubernetes namespace of the service under test
#   SERVICE_NAME       Container / deployment name of the service under test
#
# If PROMETHEUS_URL is reachable, real metrics are collected.
# Falls back to synthetic metrics derived from JTL if Prometheus is unavailable.

set -euo pipefail

JTL=""
START=""
END=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jtl)    JTL="$2";    shift 2 ;;
    --start)  START="$2";  shift 2 ;;
    --end)    END="$2";    shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

[[ -z "$OUTPUT" ]] && { echo "--output is required" >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT")"

PROMETHEUS_URL="${PROMETHEUS_URL:-}"
SERVICE_NAMESPACE="${SERVICE_NAMESPACE:-}"
SERVICE_NAME="${SERVICE_NAME:-}"

python3 - "$JTL" "$START" "$END" "$OUTPUT" "$PROMETHEUS_URL" "$SERVICE_NAMESPACE" "$SERVICE_NAME" <<'PYEOF'
import sys, csv, json, math, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

jtl_path, start_iso, end_iso, out_path, prom_url, svc_ns, svc_name = sys.argv[1:]

def parse_iso(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))

def to_iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

try:
    start_dt = parse_iso(start_iso)
    end_dt   = parse_iso(end_iso)
except Exception:
    end_dt   = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(minutes=5)

start_ts   = int(start_dt.timestamp())
end_ts     = int(end_dt.timestamp())
duration_s = max(end_ts - start_ts, 60)
step       = max(15, duration_s // 60)

# ── Parse JTL ─────────────────────────────────────────────────────────────────

total = errors = total_latency = 0
if jtl_path:
    try:
        with open(jtl_path, newline='') as f:
            for row in csv.DictReader(f):
                total += 1
                total_latency += int(row.get('elapsed', 0))
                if row.get('success', 'true').lower() == 'false':
                    errors += 1
    except Exception as e:
        print(f"JTL parse warning: {e}", file=sys.stderr)

avg_ms    = total_latency // total if total else 0
error_pct = round(errors / total * 100, 2) if total else 0.0
print(f"JTL: {total} requests | {errors} errors ({error_pct}%) | avg {avg_ms}ms", file=sys.stderr)

# ── Prometheus queries ────────────────────────────────────────────────────────

def prom_query_range(base, query, start, end, step_s, timeout=10):
    params = urllib.parse.urlencode({'query': query, 'start': start, 'end': end, 'step': step_s})
    with urllib.request.urlopen(f"{base}/api/v1/query_range?{params}", timeout=timeout) as r:
        body = json.loads(r.read())
    if body.get('status') != 'success':
        raise RuntimeError(body.get('error', 'unknown'))
    results = body['data']['result']
    if not results:
        raise RuntimeError("empty result set")
    by_ts: dict[int, list[float]] = {}
    for series in results:
        for ts_str, val_str in series['values']:
            try:
                by_ts.setdefault(int(float(ts_str)), []).append(float(val_str))
            except ValueError:
                pass
    return sorted((ts, sum(vs) / len(vs)) for ts, vs in by_ts.items())

def pts(pairs):
    return [{'t': to_iso(datetime.fromtimestamp(ts, tz=timezone.utc)), 'v': round(v, 4)} for ts, v in pairs]

def cpu_query():
    if svc_ns and svc_name:
        return f'rate(container_cpu_usage_seconds_total{{namespace="{svc_ns}",container="{svc_name}",container!="POD"}}[1m]) * 100'
    return "100 - (avg by(instance)(irate(node_cpu_seconds_total{mode='idle'}[1m])) * 100)"

def mem_query():
    if svc_ns and svc_name:
        return (f'container_memory_working_set_bytes{{namespace="{svc_ns}",container="{svc_name}",container!="POD"}}'
                f' / on() group_left clamp_min(container_spec_memory_limit_bytes{{namespace="{svc_ns}",container="{svc_name}",container!="POD"}}, 1) * 100')
    return "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"

def restarts_query():
    if svc_ns and svc_name:
        return f'increase(kube_pod_container_status_restarts_total{{namespace="{svc_ns}",container="{svc_name}"}}[{duration_s}s])'
    return None

# ── Collect real metrics ───────────────────────────────────────────────────────

use_real = False
series = {}

if prom_url:
    try:
        print(f"Querying Prometheus at {prom_url} (ns={svc_ns or '*'} svc={svc_name or '*'})", file=sys.stderr)
        cpu_pairs = prom_query_range(prom_url, cpu_query(), start_ts, end_ts, step)
        mem_pairs = prom_query_range(prom_url, mem_query(), start_ts, end_ts, step)
        series['cpu_usage']     = {'label': f'CPU Usage ({svc_name or "node"})',    'unit': '%',  'threshold': {'type': 'alert', 'max': 80},   'points': pts(cpu_pairs)}
        series['memory_usage']  = {'label': f'Memory Usage ({svc_name or "node"})', 'unit': '%',  'threshold': {'type': 'alert', 'max': 85},   'points': pts(mem_pairs)}
        rq = restarts_query()
        if rq:
            try:
                series['pod_restarts'] = {'label': f'Pod Restarts ({svc_name})', 'unit': 'count', 'threshold': {'type': 'fail', 'max': 1}, 'points': pts(prom_query_range(prom_url, rq, start_ts, end_ts, step))}
            except Exception as e:
                print(f"  restarts skipped: {e}", file=sys.stderr)
        series['error_rate']        = {'label': 'HTTP Error Rate',    'unit': '%',  'threshold': {'type': 'fail',  'max': 1},    'points': [{'t': to_iso(start_dt), 'v': error_pct}, {'t': to_iso(end_dt), 'v': error_pct}]}
        series['avg_response_time'] = {'label': 'Avg Response Time',  'unit': 'ms', 'threshold': {'type': 'alert', 'max': 2000}, 'points': [{'t': to_iso(start_dt), 'v': avg_ms},   {'t': to_iso(end_dt), 'v': avg_ms}]}
        use_real = True
        print(f"  CPU: {len(cpu_pairs)} pts | Memory: {len(mem_pairs)} pts", file=sys.stderr)
    except Exception as e:
        print(f"Prometheus unavailable — synthetic fallback: {e}", file=sys.stderr)

# ── Synthetic fallback ────────────────────────────────────────────────────────

if not use_real:
    lf = min(total / 500, 1.0) if total else 0.3
    def mkseries(base, var, step_s=30):
        pts_list, t, i = [], start_dt, 0
        while t <= end_dt:
            pts_list.append({'t': to_iso(t), 'v': round(max(0, min(100, base + var * math.sin(i * 0.4))), 2)})
            t += timedelta(seconds=step_s); i += 1
        return pts_list
    series = {
        'cpu_usage':          {'label': 'CPU Usage (synthetic)',          'unit': '%',  'threshold': {'type': 'alert', 'max': 80},   'points': mkseries(20 + lf * 55, 6)},
        'memory_usage':       {'label': 'Memory Usage (synthetic)',       'unit': '%',  'threshold': {'type': 'alert', 'max': 85},   'points': mkseries(35 + lf * 20, 3)},
        'error_rate':         {'label': 'HTTP Error Rate',                'unit': '%',  'threshold': {'type': 'fail',  'max': 1},    'points': mkseries(error_pct, 0.05)},
        'avg_response_time':  {'label': 'Avg Response Time',              'unit': 'ms', 'threshold': {'type': 'alert', 'max': 2000}, 'points': mkseries(avg_ms, avg_ms * 0.15)},
    }

with open(out_path, 'w') as f:
    json.dump({'schema': 'nextops-metrics/v1', 'window': {'start': to_iso(start_dt), 'end': to_iso(end_dt)}, 'series': series}, f, indent=2)

print(f"Written to {out_path} [{'Prometheus' if use_real else 'synthetic'}]", file=sys.stderr)
PYEOF
