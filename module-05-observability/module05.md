# Module 05 — Observability & Troubleshooting

## Objective

Set up monitoring for the Kubernetes training cluster, visualize resource usage across the student namespaces, and create a dashboard and an alert for failures of the Kyverno `require-readonly-rootfs` audit. The lab includes both metric-based monitoring and log-based detection.

## Environment

- Kubernetes: single-node `kind` cluster `k8s-security`, Kubernetes v1.29.2 (WSL2 + Docker).
- Namespaces: `mentor`, `student01`, `student02`, `student03`, `monitoring`, `kyverno`.
- Kyverno: chart 3.3.5, application v1.13.3; `require-readonly-rootfs` in **Audit** mode, with rules that validate Pod containers and autogen rules for controllers.
- Monitoring: `prometheus-community/kube-prometheus-stack` chart **89.2.0** (release `monitoring`); Grafana and Prometheus.
- Logging: `grafana/loki` chart **7.3.0**, Loki **3.6.12**; `grafana/alloy` chart **1.14.1**, Alloy **1.21.1**.

> This is an educational environment. Versions and configuration are pinned for reproducibility, not offered as production hardening guidance. In particular, some pre-existing lab components have Kubernetes-version compatibility caveats.

## Files

| File | Purpose |
|---|---|
| `prometheus-values.yaml` | Reduced kube-prometheus-stack configuration for the lab |
| `kyverno-servicemonitor.yaml` | Scrape Kyverno policy-result metrics |
| `student-workloads.yaml` | Test Deployments in `student01`–`student03` |
| `loki-values.yaml` | Loki single-binary deployment and filesystem storage |
| `alloy-values.yaml` | Alloy Pod log collection and Loki output |
| `policyreport-exporter.py` | Read PolicyReports and emit audit failures as JSON to stdout |
| `policyreport-exporter-configmap.yaml` | Python script packaged as a ConfigMap |
| `policyreport-exporter.yaml` | Exporter ServiceAccount, RBAC and Deployment |
| `student-resources-dashboard.json` | Student namespace resource dashboard exported from Grafana |
| `kyverno-audit-dashboard.json` | Kyverno metrics and logs dashboard exported from Grafana |

The exported Grafana JSON files should be re-exported after changing panels. Grafana alert rules were created in the UI and are **not automatically included in dashboard exports**.

## 1. Install monitoring

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --version 89.2.0 \
  --namespace monitoring --create-namespace \
  -f prometheus-values.yaml

kubectl get pods -n monitoring
```

Lab-specific settings in `prometheus-values.yaml`:

- Grafana enabled with an internal `ClusterIP` service.
- Chart Alertmanager disabled; Grafana-managed alert rules are used instead.
- Default Prometheus rule bundles disabled.
- etcd, scheduler and controller-manager scrape components disabled for this kind environment.
- Prometheus retention: `2d`, with reduced resource requests and a 1 GiB memory limit.
- Grafana setting `grafana.ini.plugins.preinstall_auto_update: false` avoids attempts to update a bundled plugin on a read-only filesystem.

Access Grafana using a port-forward:

```bash
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
```

Open `http://localhost:3000`. Use the credentials configured for the Helm release; do not store passwords in this repository.

### Kyverno metrics

```bash
kubectl apply -f kyverno-servicemonitor.yaml
kubectl get servicemonitor -n monitoring
```

The ServiceMonitor selects the Kyverno admission-controller metrics service in namespace `kyverno` on the named port `metrics-port` and carries `release: monitoring` so the installed Prometheus discovers it.

Verify in Grafana Explore → Prometheus:

```promql
count by (__name__) ({__name__=~"kyverno_.*"})
```

Example metric: `kyverno_policy_results_total` with `policy_name`, `rule_result`, `resource_namespace`, and other labels.

### Student test workloads

```bash
kubectl apply -f student-workloads.yaml
kubectl get pods -n student01
kubectl get pods -n student02
kubectl get pods -n student03
```

Each namespace has an nginx workload. Student Pods receive an Istio sidecar through the namespace injection setup from Module 04. CPU/memory queries therefore include the application and sidecar containers.

## 2. Student namespace dashboard

Grafana dashboard: **Kubernetes — Student Namespace Resources**.

**CPU usage (cores):**

```promql
sum by (namespace) (
  rate(container_cpu_usage_seconds_total{
    namespace=~"student01|student02|student03",
    container!="", container!="POD", image!=""
  }[5m])
)
```

**Memory working set (bytes):**

```promql
sum by (namespace) (
  container_memory_working_set_bytes{
    namespace=~"student01|student02|student03",
    container!="", container!="POD", image!=""
  }
)
```

Save and export the dashboard to `student-resources-dashboard.json`. CPU values are in cores (`0.001` core = `1` millicore); memory is displayed in MiB/GiB by Grafana.

## 3. Kyverno metric-based dashboard and alert

Dashboard: **Kyverno — Readonly Root Filesystem Audit**.

**Panel: `Readonly RootFS — Audit Failure Events (Counter)`** (Bar gauge, Instant):

```promql
sum by (resource_namespace) (
  kyverno_policy_results_total{
    policy_name="require-readonly-rootfs",
    rule_result="fail",
    resource_namespace=~"student01|student02|student03"
  }
)
```

This is a **counter of policy evaluation results**, **not** the number of currently noncompliant Pods. A Deployment, ReplicaSet and Pod can each appear in PolicyReports.

**Panel: `Readonly RootFS — New Audit Failures (5m)`** (Time series):

```promql
sum by (resource_namespace) (
  increase(kyverno_policy_results_total{
    policy_name="require-readonly-rootfs",
    rule_result="fail",
    resource_namespace=~"student01|student02|student03"
  }[5m])
)
```

`increase()` can return fractional values because Prometheus extrapolates the counter samples to the full query window.

**Grafana-managed alert:** `Kyverno Readonly RootFS Audit Failure`

```promql
sum(
  increase(kyverno_policy_results_total{
    policy_name="require-readonly-rootfs",
    rule_result="fail",
    resource_namespace=~"student01|student02|student03"
  }[5m])
) or vector(0)
```

- Data source: Prometheus.
- Threshold: **IS ABOVE 0**; pending period **0s**; evaluation interval **1m**.
- Folder: `Kubernetes Monitoring`; evaluation group: `kyverno-audit`.
- Tested: new Audit FAIL generated a positive result, and the rule entered **Firing**.
- `or vector(0)` gives a zero-valued fallback instead of an absent series when there are no matching failures.

## 4. Install Loki

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm template loki grafana/loki \
  --version 7.3.0 --namespace monitoring \
  -f loki-values.yaml > /tmp/module05-loki-rendered.yaml

helm upgrade --install loki grafana/loki \
  --version 7.3.0 --namespace monitoring \
  -f loki-values.yaml

kubectl rollout status statefulset/loki -n monitoring --timeout=180s
kubectl get pvc -n monitoring
```

The lab uses single-binary Loki with one replica, local filesystem storage, a 5 GiB PVC, and no gateway, canary or caches. The chart's Helm tests are disabled because the canary is disabled (`test.enabled: false`), avoiding: `Helm test requires the Loki Canary to be enabled`.

Verify the API:

```bash
kubectl port-forward -n monitoring svc/loki 3100:3100
# In another terminal:
curl -sS http://localhost:3100/ready
```

Expected output: `ready`.

## 5. Install Alloy and connect Loki to Grafana

```bash
helm template alloy grafana/alloy \
  --version 1.14.1 --namespace monitoring \
  -f alloy-values.yaml > /tmp/module05-alloy-rendered.yaml

helm upgrade --install alloy grafana/alloy \
  --version 1.14.1 --namespace monitoring \
  -f alloy-values.yaml

kubectl get daemonsets -n monitoring
kubectl logs -n monitoring daemonset/alloy -c alloy --tail=50
```

In this single-node kind cluster, the Alloy DaemonSet has one Pod. Alloy uses Kubernetes Pod discovery and `loki.source.kubernetes` to read container stdout/stderr via the Kubernetes API, with Loki at:

```text
http://loki.monitoring.svc.cluster.local:3100/loki/api/v1/push
```

Grafana → Connections → Data sources → Add data source → **Loki**:

```text
URL: http://loki.monitoring.svc.cluster.local:3100
```

Check Grafana Explore → Loki:

```logql
{namespace="kyverno"}
```

Inspect available labels:

```bash
curl -sG http://localhost:3100/loki/api/v1/labels
```

Expected labels include `namespace`, `pod`, `container`, `instance`, `job`, and `service_name`.

## 6. Why an exporter is needed for log-based auditing

The following LogQL query did **not** find the readonly-rootfs rule in the observed Kyverno container logs:

```logql
{namespace="kyverno"} |= "require-readonly-rootfs"
```

Kyverno Audit failures are reliably available from Kubernetes **PolicyReports**, not necessarily as a distinct stdout message for every failure. Merely installing Loki does not create missing messages. To meet the lab's log-search requirement, a small exporter reads PolicyReports and writes structured JSON records into **its own Pod logs**.

### Deploy the PolicyReport exporter

```bash
kubectl apply -f policyreport-exporter-configmap.yaml
kubectl apply -f policyreport-exporter.yaml

kubectl auth can-i list policyreports -n student01 \
  --as=system:serviceaccount:monitoring:policyreport-exporter

kubectl rollout status deployment/policyreport-exporter \
  -n monitoring --timeout=120s

kubectl logs -n monitoring deployment/policyreport-exporter --tail=20
```

Expected access-check result: `yes`.

Exporter behavior:

1. Poll namespaced `wgpolicyk8s.io/v1alpha2` PolicyReports for `student01`, `student02`, `student03` every 30 seconds.
2. Select `Pod` results where `policy=require-readonly-rootfs` and `result=fail`.
3. Log structured JSON (`event=kyverno_audit_failure`, original `namespace`, `pod`, `policy`, `rule`, `message`, timestamp).
4. Deduplicate unchanged violations in process memory. This avoids repeated log entries at each poll but **does not survive a restart**.

One initial test produced one JSON log line per student namespace:

```text
student01 → student-workload-… → require-readonly-rootfs FAIL
student02 → student-workload-… → require-readonly-rootfs FAIL
student03 → student-workload-… → require-readonly-rootfs FAIL
```

The `ClusterRole` can **list** PolicyReports and cannot change them. It is cluster-scoped even though the program reads only three namespaces; a more restrictive deployment could use per-namespace Roles and RoleBindings.

**Reproducibility warning:** `policyreport-exporter-configmap.yaml` is generated from the Python file, not dynamically linked to it. After editing `policyreport-exporter.py`, regenerate and reapply the ConfigMap and restart the Deployment:

```bash
kubectl create configmap policyreport-exporter -n monitoring \
  --from-file=exporter.py=policyreport-exporter.py \
  --dry-run=client -o yaml > policyreport-exporter-configmap.yaml
kubectl apply -f policyreport-exporter-configmap.yaml
kubectl rollout restart deployment/policyreport-exporter -n monitoring
```

### Log queries

Show raw audit events:

```logql
{namespace="monitoring", container="exporter"}
| json
| event="kyverno_audit_failure"
| policy="require-readonly-rootfs"
| __error__=""
```

The Loki **stream label** `namespace="monitoring"` identifies the exporter's Pod; the **JSON field** `namespace` identifies the student Pod that failed the check. Loki may rename the parsed field to `namespace_extracted` to avoid collision with the stream label.

## 7. Loki panels on the existing Kyverno dashboard

Added two panels to **Kyverno — Readonly Root Filesystem Audit**, alongside the two Prometheus panels.

**Panel: `Readonly RootFS — Log Events by Namespace`** (Bar gauge, **Instant** query):

```logql
sum by (namespace_extracted) (
  count_over_time(
    {namespace="monitoring", container="exporter"}
    | json
    | event="kyverno_audit_failure"
    | policy="require-readonly-rootfs"
    | __error__=""
    [24h]
  )
)
```

At verification, the query returned three rows: `student01=1`, `student02=1`, `student03=1`. With Grafana's **Rows to fields** transformation:

| Input field | Use as |
|---|---|
| `Time` | Ignore |
| `namespace_extracted` | Field name |
| `Value #A` | Field value |

This produces three bars, each named for a student namespace. **A `[24h]` count is not a running total forever**: events expire from the query window. A fixed 24-hour window is intentional for this lab panel.

**Panel: `Readonly RootFS — Audit Failure Logs`** (Logs visualization):

```logql
{namespace="monitoring", container="exporter"}
| json
| event="kyverno_audit_failure"
| policy="require-readonly-rootfs"
| __error__=""
```

Use **Last 24 hours** (or an absolute range that contains the events) when reviewing previously emitted records. A short range may legitimately show `No data`.

Save and export the updated dashboard as `kyverno-audit-dashboard.json`.

## 8. Grafana alert from Loki logs

**Grafana-managed alert:** `Kyverno Readonly RootFS Log Failure`.

```logql
sum(
  count_over_time(
    {namespace="monitoring", container="exporter"}
    | json
    | event="kyverno_audit_failure"
    | policy="require-readonly-rootfs"
    | __error__=""
    [5m]
  )
) or vector(0)
```

- Data source: **Loki**. Although it queries Loki, it is listed under **Grafana-managed → Kubernetes Monitoring → kyverno-audit**, **not** under Loki-native alert rules.
- Threshold: **IS ABOVE 0**; pending **0s**, evaluation **1m**, keep firing **0s**.
- Suggested labels: `severity=warning`, `source=loki`, `policy=require-readonly-rootfs`.
- Routing/contact point: `Kyverno Audit Notifications` was selected in the UI. **External delivery was not independently verified.** A saved contact point alone does not prove that email, Telegram or another transport is configured.
- Observed result: **Firing**, with the Loki query yielding a positive value.

To produce another event for testing, create a new Pod with a unique name in a student namespace and `readOnlyRootFilesystem: false`, then confirm it receives the required Istio sidecar and passes the Module 04 admission constraints. Verify the new PolicyReport, exporter stdout, Loki log line and alert state. Delete the test Pod after validation. Existing log events can keep the alert firing until they leave its five-minute window.

## 9. Troubleshooting

### Grafana Prometheus data source/plugin issue

Symptom: Grafana failed to query the Prometheus data source; plugin startup logged an update failure on a read-only filesystem (`unlinkat ... read-only file system`).

Fix in `prometheus-values.yaml`:

```yaml
grafana:
  grafana.ini:
    plugins:
      preinstall_auto_update: false
```

Apply via `helm upgrade` and verify `Successfully queried the Prometheus API` in Grafana.

### Loki chart validation error

Symptom:

```text
Helm test requires the Loki Canary to be enabled
```

The lab disables the canary. Add:

```yaml
lokiCanary:
  enabled: false
test:
  enabled: false
```

Then rerun `helm template` and the upgrade.

### Kyverno `fsnotify` / inotify exhaustion

Observed in Kyverno admission and reports controller logs:

```text
failed to create fsnotify watcher: too many open files
```

WSL values observed:

```text
fs.inotify.max_user_instances = 128
fs.inotify.max_user_watches = 524288
ulimit -n = 10240
```

Tested remediation in WSL Ubuntu:

```bash
sudo sysctl -w fs.inotify.max_user_instances=512
sysctl fs.inotify.max_user_instances
```

Afterwards the log rate declined, and recent-minute queries returned no matches. This supports, but does not conclusively prove, that the inotify instance limit was the cause.

For persistence (if confirmed appropriate for the local WSL installation):

```bash
echo 'fs.inotify.max_user_instances=512' | \
  sudo tee /etc/sysctl.d/99-k8s-inotify.conf
sudo sysctl --system
```

Check newly appearing errors with:

```logql
sum(
  count_over_time(
    {namespace="kyverno"} |= "failed to create fsnotify watcher" [1m]
  )
) or vector(0)
```

### No data in Loki panel

- Confirm `policyreport-exporter` is running and has logged an event.
- Confirm the Alloy DaemonSet and Loki Pod are Ready.
- Search raw logs in Grafana Explore before trying aggregate LogQL expressions.
- Expand the time range to include the original event timestamp.
- Confirm the parsed namespace field is `namespace_extracted` when the stream itself also has a `namespace` label.
- For an Instant Bar gauge, use a look-back window such as `[24h]` instead of `[5m]` if the last event is old.

## 10. Limitations and next improvements

- The metric-based alert detects **new evaluations**, not continuously failing Pods.
- The exporter detects **results currently present in PolicyReports** at poll time; short-lived violations can be missed between polls.
- The exporter stores deduplication state in memory; a restart produces duplicate historical-looking log events for still-failing Pods. The single replica and `Recreate` update strategy reduce concurrent duplicates but do not provide durable exactly-once delivery.
- Log timestamps represent **export time**, not necessarily the original time of the policy evaluation.
- Loki receives exporter Pod logs, not direct readonly-rootfs failures from every application Pod. The exported source is explicitly Kyverno PolicyReports.
- A locally stored Loki PVC is appropriate for a disposable learning environment, not a highly available logging service.
- Grafana dashboards are exportable as JSON, but the two Grafana-managed alert rules need **separate export/provisioning** or documented UI recreation.
- Notification routing was configured for the lab, but **external notification delivery has not been verified**.

## Verification checklist

- [x] Prometheus/Grafana running; student namespace CPU and memory panels operational.
- [x] Kyverno ServiceMonitor created and policy-result metrics visible in Prometheus.
- [x] Kyverno metric-based alert observed in `Firing`.
- [x] Loki Ready (`/ready` → `ready`), PVC bound, Alloy DaemonSet Ready.
- [x] Pod logs visible in Loki/Grafana Explore.
- [x] Exporter emitted three JSON `kyverno_audit_failure` messages for `student01`–`student03`.
- [x] Existing Kyverno dashboard extended with Loki event-count and raw-log panels.
- [x] Loki log-based Grafana alert observed in `Firing`.
- [ ] Export the final dashboard JSON after any subsequent UI edits, if not already done.
- [ ] Export/provision both Grafana alert rules for full environment recreation.
- [ ] Validate external notification delivery only if desired.

## Git check

From the repository root:

```bash
git status --short
git diff --check
git add module-05-observability/
git commit -m "Document module 05 observability and audit logging"
```

Keep the Git review step before committing; do not include `:Zone.Identifier`, malformed stray filenames, or temporary test Pod manifests unless they are intentionally retained for reproducible exercises.
