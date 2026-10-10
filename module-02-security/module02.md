# Module 02 – Security & Policy as Code

Practical laboratory assignment focusing on configuring a secure, isolated multi-tenant Kubernetes environment in WSL 2.

## Contents of this directory:
- `rbac.yaml` — Roles and RoleBindings for mentor and student namespaces.
- `restrict-root-user.yaml` — Kyverno validation policy blocking root container execution.
- `add-owner-label.yaml` — Kyverno mutation policy for automatic owner label injection.

## Execution Steps

### 1. Environment & Cluster Prerequisites
- Ensure your workstation is fully prepared with WSL 2, Docker, `kubectl`, and `kind` as described in the main **[Setup Guide](../setup.md)**.
- Verify that the local cluster named `k8s-security` is up and running, and your current context is correctly configured:
  ```bash
  kubectl cluster-info
  kubectl config current-context
  ```

### 2. Namespaces & RBAC (Role-Based Access Control)
- Create isolated student namespaces for multi-tenancy demonstration:
  ```bash
  kubectl create namespace student01
  kubectl create namespace student02
  kubectl create namespace student03
  ```
- Apply the RBAC manifest to establish proper permission boundaries and role bindings for users and the mentor:
  ```bash
  kubectl apply -f rbac.yaml
  ```
- Verify that roles and role bindings have been correctly created within the respective namespaces:
  ```bash
  kubectl get roles,rolebindings --all-namespaces
  ```

### 3. Policy-as-Code (Kyverno)
- Add the Kyverno Helm repository, update local charts, and install Kyverno v3.3.5 into its dedicated namespace:
  ```bash
  helm repo add kyverno https://kyverno.github.io/kyverno/
  helm repo update
  kubectl create namespace kyverno
  helm install kyverno kyverno/kyverno -n kyverno --version 3.3.5
  ```
- Wait for all Kyverno components (admission controller, background controller, reports controller) to be fully ready:
  ```bash
  kubectl rollout status deployment kyverno-admission-controller -n kyverno
  ```
- Apply the validation security policy to block containers running with root privileges:
  ```bash
  kubectl apply -f restrict-root-user.yaml
  ```
- Apply the mutation policy for automatic injection of owner labels into workloads:
  ```bash
  kubectl apply -f add-owner-label.yaml
  ```
- Verify that both Kyverno cluster policies are successfully active and functioning:
  ```bash
  kubectl get clusterpolicies
  ```
