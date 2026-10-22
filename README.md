# Kubernetes in Production — Homeworks & Labs

Repository containing practical laboratory assignments and homework projects for the **Kubernetes in Production** course.

The labs cover Kubernetes security, GitOps, service mesh, observability, and troubleshooting in a local Kubernetes environment.

---

## Environment Setup

Before starting the modules, prepare WSL 2, Docker, `kubectl`, and `kind` using the following guide:

**[📖 Environment Setup Guide (WSL 2, Docker, kubectl, kind)](./setup.md)**

---

## Course Modules & Assignments

### Module 02: Security & Policy as Code

**[📖 Module 02 Documentation](./module-02-security/module02.md)**

**Topics:**
- X.509 certificates and Kubernetes authentication
- Role-Based Access Control (RBAC) and namespace isolation
- Student and mentor access using separate kubeconfigs
- Kyverno validation and mutation policies
- Read-only root filesystem audit and automatic Pod labeling

**Manifests and documentation:** `module-02-security/`

### Module 03: GitOps & Platform Management

**[📖 Module 03 Documentation](./module-03-platform/module03.md)**

**Topics:**
- GitOps concepts and declarative configuration
- Argo CD installation
- Kubernetes Custom Resource Definitions (CRDs)
- Argo CD application management

**Manifests and documentation:** `module-03-platform/`

### Module 04: Service Mesh

**[📖 Module 04 Documentation](./module-04-service-mesh/module04.md)**

**Topics:**
- Istio service mesh installation
- Envoy sidecar injection
- Namespace-based automatic injection
- Kyverno policies for student workloads
- Validation that student Pods include the Istio sidecar

**Manifests and documentation:** `module-04-service-mesh/`

### Module 05: Observability & Troubleshooting

**[📖 Module 05 Documentation](./module-05-observability/module05.md)**

**Topics:**
- Prometheus and Grafana monitoring
- CPU and memory dashboards for student namespaces
- Kyverno PolicyReports and audit metrics
- Prometheus-based alerting
- Centralized logging with Loki and Grafana Alloy
- Python PolicyReport exporter
- LogQL dashboards and log-based alerting
- Troubleshooting Grafana, Helm, and Linux inotify limits

**Manifests and documentation:** `module-05-observability/`

---

## Technology Stack

| Area | Technologies |
| --- | --- |
| Local environment | WSL 2, Ubuntu, Docker, kind |
| Kubernetes tooling | Kubernetes, kubectl, Helm |
| Security | X.509, Kubernetes RBAC, Kyverno |
| GitOps | Argo CD |
| Service mesh | Istio, Envoy |
| Monitoring | Prometheus, Grafana |
| Logging | Loki, Grafana Alloy |
| Scripting and configuration | Python, YAML |

---

## Repository Structure

```text
kubernetes-production-practice/
├── README.md
├── setup.md
├── module-02-security/
│   └── module02.md
├── module-03-platform/
│   └── module03.md
├── module-04-service-mesh/
│   └── module04.md
└── module-05-observability/
    └── module05.md
```

Each module directory also contains the manifests, Helm values, scripts, or exported dashboards used in its exercises, where applicable.

---

## Notes

This repository is intended for **education and hands-on practice**. Configurations are designed for a local lab environment, not as production-ready deployment templates. Additional security, persistence, scaling, and availability measures may be needed for real-world use.
