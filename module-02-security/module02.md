# Module 02 – Security & Policy as Code

Practical laboratory assignment focusing on configuring a secure, isolated multi-tenant Kubernetes environment in WSL 2.

## Contents of This Directory

- `rbac.yaml` — ClusterRole, Roles, and RoleBindings for mentor and student namespaces.
- `require-readonly-rootfs.yaml` — Kyverno audit policy for read-only root filesystems.
- `add-person-label.yaml` — Kyverno mutation policy for automatic `person` label injection.

## Working Directory

From the repository root, navigate to the Module 02 directory before running the commands:

```bash
cd module-02-security
```

All relative file paths in this guide assume this working directory.

## Execution Steps

### 1. Environment & Cluster Prerequisites

Ensure your workstation is prepared with WSL 2, Docker, `kubectl`, and `kind` as described in the [Setup Guide](../setup.md).

Verify that the `k8s-security` cluster is running and the current context is correct:

```bash
kubectl cluster-info
kubectl config current-context
```

### 2. Namespaces & Certificate-Based Authentication (RBAC)

#### Create namespaces

Create isolated namespaces for the mentor and students:

```bash
kubectl create namespace mentor
kubectl create namespace student01
kubectl create namespace student02
kubectl create namespace student03
```

Verify the namespaces:

```bash
kubectl get namespaces
```

#### Extract the cluster CA certificate and key

> **Lab only:** The following steps extract the Kubernetes cluster CA private key from the kind control-plane container. Do not use this approach in production. Keep `ca.key`, generated private keys, certificates, and kubeconfig files out of version control.

```bash
docker cp k8s-security-control-plane:/etc/kubernetes/pki/ca.crt ./ca.crt
docker cp k8s-security-control-plane:/etc/kubernetes/pki/ca.key ./ca.key
```

#### Generate private keys and CSRs

Create private keys and Certificate Signing Requests (CSRs) for the mentor and students:

```bash
# Mentor
openssl genrsa -out mentor.key 2048
openssl req -new -key mentor.key -out mentor.csr -subj "/CN=mentor/O=teachers"

# Student 01
openssl genrsa -out student01.key 2048
openssl req -new -key student01.key -out student01.csr -subj "/CN=student01/O=students"

# Student 02
openssl genrsa -out student02.key 2048
openssl req -new -key student02.key -out student02.csr -subj "/CN=student02/O=students"

# Student 03
openssl genrsa -out student03.key 2048
openssl req -new -key student03.key -out student03.csr -subj "/CN=student03/O=students"
```

#### Sign client certificates

Sign each CSR using the cluster CA, with certificates valid for 365 days:

```bash
for user in mentor student01 student02 student03; do
  openssl x509 -req -in "${user}.csr" -CA ca.crt -CAkey ca.key \
    -CAcreateserial -out "${user}.crt" -days 365
done
```

#### Generate dedicated kubeconfig files

Retrieve the Kubernetes API server endpoint from the current context:

```bash
SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
echo "$SERVER"
```

Create the mentor kubeconfig:

```bash
kubectl config --kubeconfig=mentor.kubeconfig set-cluster k8s-security --server="$SERVER" --certificate-authority=ca.crt --embed-certs=true
kubectl config --kubeconfig=mentor.kubeconfig set-credentials mentor --client-certificate=mentor.crt --client-key=mentor.key --embed-certs=true
kubectl config --kubeconfig=mentor.kubeconfig set-context mentor-context --cluster=k8s-security --user=mentor --namespace=mentor
kubectl config --kubeconfig=mentor.kubeconfig use-context mentor-context
```

Create kubeconfig files for the students:

```bash
for student in student01 student02 student03; do
  kubectl config --kubeconfig="${student}.kubeconfig" set-cluster k8s-security --server="$SERVER" --certificate-authority=ca.crt --embed-certs=true
  kubectl config --kubeconfig="${student}.kubeconfig" set-credentials "$student" --client-certificate="${student}.crt" --client-key="${student}.key" --embed-certs=true
  kubectl config --kubeconfig="${student}.kubeconfig" set-context "${student}-context" --cluster=k8s-security --user="$student" --namespace="$student"
  kubectl config --kubeconfig="${student}.kubeconfig" use-context "${student}-context"
done
```

#### Apply and verify RBAC

Apply the RBAC manifest to configure roles and role bindings:

```bash
kubectl apply -f rbac.yaml
```

Verify RBAC resources:

```bash
kubectl get clusterrole mentor-full-access
kubectl get roles,rolebindings -A
```

> **Note:** Creating client certificates and kubeconfig files does not grant access by itself. Permissions are determined by the corresponding RBAC bindings.

#### Verify RBAC permissions

Run these checks using the dedicated user kubeconfig files, not the administrator's context:

```bash
# Mentor: write access to all student namespaces
kubectl --kubeconfig=mentor.kubeconfig auth can-i create pods -n student01
kubectl --kubeconfig=mentor.kubeconfig auth can-i create pods -n student02
kubectl --kubeconfig=mentor.kubeconfig auth can-i create pods -n student03

# Mentor: no unrestricted permissions across the cluster
kubectl --kubeconfig=mentor.kubeconfig auth can-i '*' '*' --all-namespaces

# Student01: access only to own namespace
kubectl --kubeconfig=student01.kubeconfig auth can-i create pods -n student01
kubectl --kubeconfig=student01.kubeconfig auth can-i create pods -n student02

# Student02: read-only access to student01 and default
kubectl --kubeconfig=student02.kubeconfig auth can-i get pods -n student01
kubectl --kubeconfig=student02.kubeconfig auth can-i create pods -n student01
kubectl --kubeconfig=student02.kubeconfig auth can-i get pods -n default
kubectl --kubeconfig=student02.kubeconfig auth can-i create pods -n default

# Student03: access only to own namespace
kubectl --kubeconfig=student03.kubeconfig auth can-i create pods -n student03
kubectl --kubeconfig=student03.kubeconfig auth can-i create pods -n student01
```

Expected results, in the order shown:

```text
yes
yes
yes
no
yes
no
yes
no
yes
no
yes
no
```

Verify that students do not have unrestricted cluster-wide permissions:

```bash
for user in student01 student02 student03; do
  echo "Checking $user:"
  kubectl --kubeconfig="${user}.kubeconfig" auth can-i '*' '*' --all-namespaces
done
```

Expected result: `no` for each student. These checks confirm the required access boundaries, but are not a complete audit of every possible permission or privilege escalation path.


### 3. Policy as Code (Kyverno)

#### Install Kyverno

Add the Helm repository and install Kyverno v3.3.5 in its own namespace:

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
kubectl create namespace kyverno
helm install kyverno kyverno/kyverno -n kyverno --version 3.3.5
```

Wait for the Kyverno admission controller to become ready:

```bash
kubectl rollout status deployment kyverno-admission-controller -n kyverno
```

#### Apply Kyverno policies

Apply the read-only root filesystem validation policy in Audit mode:

```bash
kubectl apply -f require-readonly-rootfs.yaml
```

Apply the policy that automatically adds the `person` label:

```bash
kubectl apply -f add-person-label.yaml
```

#### Verify policies

List installed Kyverno cluster policies:

```bash
kubectl get clusterpolicies
```

#### Test read-only root filesystem audit policy

Confirm the validation rule uses `Audit` mode:

```bash
kubectl get clusterpolicy require-readonly-rootfs \
  -o jsonpath='{.spec.rules[0].validate.failureAction}{"\n"}'
```

Expected output: `Audit`.

Create a Pod without `securityContext.readOnlyRootFilesystem: true`:

```bash
kubectl run test-rootfs -n student01 \
  --image=nginx:alpine --restart=Never
kubectl get pod test-rootfs -n student01
```

The Pod should be created despite the policy violation because the rule is in Audit mode.

Inspect its PolicyReport:

```bash
kubectl get policyreports -n student01
kubectl describe policyreports -n student01
```

Find the entry with these values:

```text
Policy:  require-readonly-rootfs
Rule:    check-readonly-rootfs
Result:  fail
```

> **Note:** PolicyReports may take a short time to appear. A `fail` result indicates an audit finding; it does not mean the Pod was rejected.

#### Test automatic person labels

Create Pods in mentor, student, and default namespaces:

```bash
kubectl run test-student -n student01 --image=nginx:alpine --restart=Never
kubectl run test-student -n student02 --image=nginx:alpine --restart=Never
kubectl run test-student -n student03 --image=nginx:alpine --restart=Never
kubectl run test-mentor -n mentor --image=nginx:alpine --restart=Never
kubectl run test-default -n default --image=nginx:alpine --restart=Never --labels="person=student"
```

Inspect assigned labels:

```bash
kubectl get pod test-student -n student01 --show-labels
kubectl get pod test-student -n student02 --show-labels
kubectl get pod test-student -n student03 --show-labels
kubectl get pod test-mentor -n mentor --show-labels
kubectl get pod test-default -n default --show-labels
```

Expected values:

| Namespace | Expected `person` label |
| --- | --- |
| `student01` | `student` |
| `student02` | `student` |
| `student03` | `student` |
| `mentor` | `mentor` |
| `default` | Absent (the explicitly supplied label is removed) |

The policy also targets Pods in other namespaces outside this list to remove a supplied `person` label during admission. These tests verify the representative `default` case.

#### Clean up test Pods

```bash
kubectl delete pod test-rootfs -n student01 --ignore-not-found
kubectl delete pod test-student -n student01 --ignore-not-found
kubectl delete pod test-student -n student02 --ignore-not-found
kubectl delete pod test-student -n student03 --ignore-not-found
kubectl delete pod test-mentor -n mentor --ignore-not-found
kubectl delete pod test-default -n default --ignore-not-found
```
