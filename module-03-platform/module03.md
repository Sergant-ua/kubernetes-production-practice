# Module 03 – Platform Engineering

Practical laboratory assignment for managing Kubernetes configuration through GitOps using **Argo CD** and **Helm**. This module migrates the two Kyverno policies from Module 02 into a Helm chart and configures automated synchronization from GitHub.

## Contents of this directory

- `module03.md` — installation, configuration, and verification guide.
- `argocd/application.yaml` — Argo CD Application referencing the Helm chart in Git.
- `helm/kyverno-policies/Chart.yaml` — Helm chart metadata.
- `helm/kyverno-policies/values.yaml` — configurable policy settings.
- `helm/kyverno-policies/templates/require-readonly-rootfs.yaml` — Kyverno validation policy (Audit mode).
- `helm/kyverno-policies/templates/add-person-label.yaml` — Kyverno Pod label mutation policy.

## Working Directory

Run the following commands from the **repository root** unless otherwise indicated:

```bash
cd kubernetes-production-practice
```

> If you are already inside the repository, do not run `cd` again. Commands in this document use paths relative to the repository root.

## 1. Environment Prerequisites

Use the existing `kind` cluster from [Environment Setup](../setup.md) and the Kyverno installation and namespaces from [Module 02](../module-02-security/module02.md).

Confirm the Kubernetes context and cluster state:

```bash
kubectl config current-context
kubectl get nodes
kubectl get namespaces
```

Expected context: `kind-k8s-security`.

Check Helm and the existing Kyverno release:

```bash
helm version --short
helm list -A
kubectl get clusterpolicies
```

Do **not** uninstall Kyverno or recreate the cluster. The existing policies will be reconciled by Argo CD.

## 2. Install Argo CD

Create a dedicated namespace and install the pinned Argo CD version:

```bash
kubectl create namespace argocd

kubectl apply --server-side -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.4/manifests/install.yaml
```

> **Why Server-Side Apply?** The `applicationsets.argoproj.io` CRD is large enough that client-side `kubectl apply` can fail with `metadata.annotations: Too long`. Server-Side Apply avoids placing the whole manifest in the `last-applied-configuration` annotation. If Argo CD was partially installed using client-side apply, review field-ownership conflicts rather than blindly forcing an overwrite.

Verify the three Argo CD CRDs:

```bash
kubectl get crd | grep argoproj.io
```

Expected CRDs:

```text
applications.argoproj.io
applicationsets.argoproj.io
appprojects.argoproj.io
```

Wait for the primary components:

```bash
kubectl rollout status deployment/argocd-server -n argocd --timeout=180s
kubectl rollout status deployment/argocd-repo-server -n argocd --timeout=180s
kubectl rollout status deployment/argocd-applicationset-controller -n argocd --timeout=180s
kubectl rollout status statefulset/argocd-application-controller -n argocd --timeout=180s
kubectl get pods -n argocd
```

All Argo CD Pods should become ready. If ApplicationSet Controller repeatedly restarts, verify that `applicationsets.argoproj.io` exists and inspect the controller logs.

### Access the Argo CD Web UI

Keep the following command running in a separate WSL terminal:

```bash
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

Open **https://localhost:8080** and sign in as `admin`. Obtain the initial password in another terminal:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
echo
```

Do not commit or share the password. A browser warning about the local self-signed certificate is expected in this lab.

## 3. Create the Helm Chart

The chart lives at `module-03-platform/helm/kyverno-policies/` and contains the **same two ClusterPolicy resources** used in Module 02:

- `require-readonly-rootfs`: checks `securityContext.readOnlyRootFilesystem: true`, with `failureAction: Audit`.
- `add-person-label`: sets `person=student` in `student01`–`student03`, sets `person=mentor` in `mentor`, and removes `person` from newly admitted Pods in other namespaces.

The Helm templates use values from `values.yaml`:

```yaml
validation:
  enabled: true
  failureAction: Audit
  background: true

mutation:
  enabled: true
  background: false
  labelKey: person
  studentLabelValue: student
  mentorLabelValue: mentor
  studentNamespaces:
    - student01
    - student02
    - student03
  mentorNamespace: mentor
```

Helm templates must preserve the Kyverno expression `{{ request.object.metadata.labels.person || '' }}` as literal text in the rendered Kubernetes manifest.

### Validate the chart

```bash
helm lint ./module-03-platform/helm/kyverno-policies

helm template kyverno-policies \
  ./module-03-platform/helm/kyverno-policies \
  > /tmp/kyverno-rendered.yaml

kubectl apply --dry-run=server -f /tmp/kyverno-rendered.yaml
```

Verify that exactly two `ClusterPolicy` resources are rendered:

```bash
helm template kyverno-policies \
  ./module-03-platform/helm/kyverno-policies \
  | grep -E '^kind:|^  name:'
```

Expected names: `add-person-label` and `require-readonly-rootfs`. The `helm lint` message recommending a chart icon is informational only.

> Do not run `helm install` for this chart. Argo CD will render the chart and manage these existing cluster-scoped policies. The Kyverno controller itself remains installed as a separate Helm release.

## 4. Configure Argo CD Application

Create `module-03-platform/argocd/application.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kyverno-policies
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/Sergant-ua/kubernetes-production-practice.git
    targetRevision: module-03
    path: module-03-platform/helm/kyverno-policies
    helm:
      releaseName: kyverno-policies
  destination:
    server: https://kubernetes.default.svc
    namespace: kyverno
  syncPolicy:
    syncOptions:
      - CreateNamespace=false
```

The first sync is intentionally **manual** so that the differences between the already-running Module 02 policies and the Helm-rendered manifests can be reviewed.

Validate and create the Application:

```bash
kubectl apply --dry-run=server -f module-03-platform/argocd/application.yaml
kubectl apply -f module-03-platform/argocd/application.yaml
kubectl get applications -n argocd
```

In the Argo CD UI, open `kyverno-policies` and inspect **Diff** for both ClusterPolicies. An Argo CD tracking annotation is expected; verify that policy rules and settings remain correct before proceeding.

Perform the first **manual Sync** without `Prune` or `Force`, then verify:

```bash
kubectl get applications -n argocd
kubectl get clusterpolicies
```

Expected Application state: **Synced / Healthy**. Both Kyverno policies should remain **Ready**.

## 5. Enable Automatic GitOps Synchronization

Once the initial manual sync is successful, enable **Auto-Sync** for `kyverno-policies` in the Argo CD UI. Leave **Prune** and **Self Heal** disabled for the initial lab.

Check the resulting configuration:

```bash
kubectl get application kyverno-policies -n argocd \
  -o jsonpath='{.spec.syncPolicy.automated}{"\n"}'
```

Expected values include `enabled: true`, `prune: false`, and `selfHeal: false`.

### Verify GitHub → Argo CD → Kubernetes

Make a **non-functional change** to the description annotation in the Helm template `module-03-platform/helm/kyverno-policies/templates/require-readonly-rootfs.yaml`, for example append:

```text
Managed by Argo CD via GitOps.
```

Commit and push to the `module-03` branch:

```bash
git add module-03-platform/helm/kyverno-policies/
git commit -m "test: verify Argo CD automatic synchronization"
git push origin module-03
```

Allow Argo CD time to refresh its Git revision and synchronize automatically. Then verify:

```bash
kubectl get application kyverno-policies -n argocd \
  -o jsonpath='Sync: {.status.sync.status}{"\n"}Revision: {.status.sync.revision}{"\n"}'

git rev-parse HEAD

kubectl get clusterpolicy require-readonly-rootfs \
  -o jsonpath='{.metadata.annotations.policies\.kyverno\.io/description}{"\n"}'
```

**Success criteria:** Argo CD reports `Synced`, its revision matches the pushed commit, and the changed annotation is visible on the live ClusterPolicy.

If synchronization is delayed, request a refresh (this does not itself perform a manual sync):

```bash
kubectl annotate application kyverno-policies -n argocd \
  argocd.argoproj.io/refresh=hard --overwrite
```

## 6. Final Verification

```bash
kubectl get application kyverno-policies -n argocd
kubectl get clusterpolicies
kubectl get pods -n argocd
helm list -A
```

The Argo CD Application should be `Synced / Healthy`, and both Kyverno policies should be `Ready`. The Argo CD-managed chart is **not necessarily listed as a Helm release** in `helm list`, because Argo CD uses Helm for manifest rendering and manages the resources itself.

## References

- [Argo CD documentation](https://argo-cd.readthedocs.io/)
- [Argo CD declarative setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
- [Helm chart documentation](https://helm.sh/docs/topics/charts/)
- [Kyverno documentation](https://kyverno.io/docs/)
