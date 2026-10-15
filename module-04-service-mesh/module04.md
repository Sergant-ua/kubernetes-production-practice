# Module 04 – Service Mesh

## Objectives

1. Install Istio Service Mesh in sidecar mode.
2. Configure Kyverno policies to ensure that Pods with the label `person: student` run with an Istio sidecar container.

## 1. Prerequisites

The Kubernetes cluster and Kyverno must already be installed.

Namespaces created in Module 02:

- `mentor`
- `student01`
- `student02`
- `student03`

The `add-person-label` Kyverno policy from Module 02 assigns `person=student` to Pods in student namespaces and `person=mentor` to Pods in the mentor namespace.

```bash
kubectl get nodes
kubectl get namespaces
kubectl get clusterpolicies
```

## 2. Install Istio

Download the Istio distribution:

```bash
curl -L https://istio.io/downloadIstio | sh -
```

Enter the downloaded directory (replace `<version>` with the actual version) and install `istioctl`:

```bash
cd istio-<version>
sudo install -m 755 bin/istioctl /usr/local/bin/istioctl
istioctl version --remote=false
```

Install Istio using the `demo` profile in sidecar mode, without ingress and egress gateways:

```bash
istioctl install \
  --set profile=demo \
  --set 'components.ingressGateways[0].enabled=false' \
  --set 'components.egressGateways[0].enabled=false' \
  -y
```

Verify the control plane and admission webhooks:

```bash
kubectl get pods -n istio-system
istioctl version
kubectl get mutatingwebhookconfigurations | grep istio
```

Expected: `istiod` is Running and the Istio injection webhooks exist.

## 3. Enable Istio Injection with Kyverno

Apply `inject-istio-student-namespaces.yaml`:

```bash
kubectl apply -f inject-istio-student-namespaces.yaml
```

The policy adds `istio-injection=enabled` to the `student01`, `student02`, and `student03` namespaces when they are created or updated.

If the namespaces already exist, trigger an update to let the mutation policy act:

```bash
kubectl annotate namespace \
  student01 student02 student03 \
  module04-test="$(date +%s)" \
  --overwrite
```

Verify:

```bash
kubectl get namespaces -L istio-injection
```

Expected: `student01`, `student02`, and `student03` show `enabled`; `mentor` does not.

## 4. Enforce Istio Sidecar with Kyverno

Apply `require-istio-sidecar.yaml`:

```bash
kubectl apply -f require-istio-sidecar.yaml
kubectl get clusterpolicy require-istio-sidecar
```

This validation policy uses `failureAction: Enforce` and applies to `CREATE` requests for Pods with `person=student`. It rejects Pod creation when the `istio-proxy` container is missing. Expected policy status: `Ready`.

## 5. Positive Test

Create a Pod in a student namespace without specifying labels manually:

```bash
kubectl run test-student \
  --image=nginx:alpine \
  --restart=Never \
  -n student01
```

Verify the assigned label and injected containers:

```bash
kubectl get pod test-student -n student01 \
  -o jsonpath='{.metadata.labels.person}{" | "}{.spec.containers[*].name}{"\n"}'
```

Expected:

```text
student | test-student istio-proxy
```

Optionally inspect the proxy connection:

```bash
istioctl proxy-status
```

## 6. Negative Test

Use `test-student-no-sidecar.yaml`, which declares `person=student` but explicitly disables injection:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: test-student-no-sidecar
  namespace: student01
  labels:
    person: student
    sidecar.istio.io/inject: "false"
spec:
  containers:
    - name: nginx
      image: nginx:alpine
```

Apply it:

```bash
kubectl apply -f test-student-no-sidecar.yaml
```

Expected: Kyverno rejects the creation request with the policy message:

```text
require-istio-sidecar:
  require-sidecar-for-students: Pods with person=student must have istio-proxy container.
```

## 7. Verify Mentor Namespace

```bash
kubectl run test-mentor \
  --image=nginx:alpine \
  --restart=Never \
  -n mentor

kubectl get pod test-mentor -n mentor \
  -o jsonpath='{.metadata.labels.person}{" | "}{.spec.containers[*].name}{"\n"}'
```

Expected:

```text
mentor | test-mentor
```

## 8. Final Verification

```bash
kubectl get clusterpolicies
kubectl get namespaces -L istio-injection
kubectl get pods -n istio-system
```

Expected Kyverno policies from Modules 02 and 04:

```text
add-person-label
require-readonly-rootfs
inject-istio-student-namespaces
require-istio-sidecar
```

## 9. Cleanup

```bash
kubectl delete pod test-student -n student01 --ignore-not-found
kubectl delete pod test-mentor -n mentor --ignore-not-found
```

The negative-test Pod was rejected at admission and does not require deletion.

## Notes

- Istio injection is enabled **by namespace** for the three student namespaces; Kyverno separately validates the presence of an `istio-proxy` container **by the `person=student` label**.
- This implements the demonstrated behavior for the namespace/person mapping established in Module 02. It is **not** strictly label-only injection for arbitrary namespaces.
- Checking a container name does not prove that it is a healthy, genuine Istio proxy. `istioctl proxy-status` provides an additional operational check.
- The lab was tested using Kubernetes **v1.29.2** and Istio **v1.31.1**. This is an **unsupported version combination**, despite the successful functional tests.

## Test Results

| Test | Result |
|---|---|
| Istio sidecar injection | Passed |
| Student Pod injection in student namespaces | Passed |
| Mentor Pod without automatic injection | Passed |
| Kyverno denies student Pod without sidecar | Passed |
| Pod deletion after restricting validation to CREATE | Passed |
