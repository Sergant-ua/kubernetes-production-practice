# Module 02 – Security & Policy as Code

Practical laboratory assignment focusing on configuring a secure, isolated multi-tenant Kubernetes environment in WSL 2.

## Contents of this directory:
- `rbac.yaml` — Roles and RoleBindings for mentor and student namespaces.
- `restrict-root-user.yaml` — Kyverno validation policy blocking root container execution.
- `add-owner-label.yaml` — Kyverno mutation policy for automatic owner label injection.

## Execution Steps

### 1. Environment Setup (WSL 2 & kind)
- Install WSL 2 and Ubuntu.
- Install Docker, `kubectl`, and `kind`.
- Create a local cluster named `k8s-security`:
  ```bash
  kind create cluster --name k8s-security
  ```

### 2. Namespaces & RBAC
- Create namespaces (`student01`, `student02`, `student03`).
- Apply RBAC rules:
  ```bash
  kubectl apply -f rbac.yaml
  ```

### 3. Policy-as-Code (Kyverno)
- Install Kyverno v3.3.5 via Helm.
- Apply security policies:
  ```bash
  kubectl apply -f restrict-root-user.yaml
  kubectl apply -f add-owner-label.yaml
  ```
