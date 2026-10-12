# Module 02 – Security & Policy as Code

Practical laboratory assignment focusing on configuring a secure, isolated multi-tenant Kubernetes environment in WSL 2.

## Contents of This Directory

- `rbac.yaml` — Roles and RoleBindings for mentor and student namespaces.
- `require-readonly-rootfs.yaml` — Kyverno audit policy for read-only root filesystems.
- `add-person-label.yaml` — Kyverno mutation policy for automatic `person` label injection.

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
kubectl get roles,rolebindings --all-namespaces
```

> **Note:** Creating client certificates and kubeconfig files does not grant access by itself. Permissions are determined by the corresponding RBAC bindings.

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

