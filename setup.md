# Environment Setup Guide (WSL 2 + Docker + kind + Helm)

This guide describes how to prepare a local Kubernetes lab on Windows using WSL 2, Docker Engine, kind, and Helm. Run the commands in order to install the required tools and create a cluster for the security exercises.

**Prerequisites:** Windows with WSL 2 support, administrator access for the initial WSL installation, an internet connection, and an Ubuntu WSL distribution. Unless stated otherwise, run commands in the **Ubuntu terminal**.

## 1. WSL 2 (Ubuntu)

WSL 2 provides a Linux environment on Windows without requiring a separate virtual machine. Open **PowerShell as Administrator** to install Ubuntu:

```powershell
wsl --install
```

Verify that Ubuntu is running under **WSL version 2** (in PowerShell):

```powershell
wsl -l -v
```

> **Note:** Restart your PC if required, launch Ubuntu, and update packages.

```bash
sudo apt update && sudo apt upgrade -y
```

## 2. Docker Engine (Clean Install)

Docker runs the containers used by kind to host the Kubernetes nodes. Install Docker Engine directly inside the Ubuntu WSL distribution. First, install the packages needed to trust the official Docker repository:

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

Register the official Docker APT repository so Ubuntu can install Docker Engine packages:

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Install Docker Engine and add your user to the `docker` group so Docker commands can run without `sudo`:

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io
sudo usermod -aG docker "$USER"
```

> **Note:** Reopen your WSL session (or run `newgrp docker`) after changing group membership. Membership in the `docker` group grants root-equivalent access to the host.

Start the Docker daemon and run a test container to confirm the installation works:

```bash
sudo service docker start
docker run hello-world
```

## 3. kubectl & kind

`kubectl` is the command-line client for managing Kubernetes resources. Install it inside Ubuntu:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x ./kubectl && sudo mv ./kubectl /usr/local/bin/kubectl
```

`kind` (Kubernetes in Docker) creates local Kubernetes clusters using Docker containers as nodes. Install the kind CLI:

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind
```

## 4. Helm

Helm is the Kubernetes package manager:

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

## 5. Cluster Creation

With Docker running, create a local Kubernetes cluster named `k8s-security`. kind will also configure a `kubectl` context for this cluster:

```bash
kind create cluster --name k8s-security
```

Verify that the cluster node is ready and that system pods are running:

```bash
kubectl get nodes
kubectl get pods -A
```

The environment is ready when the node reports **Ready** and the core Kubernetes pods are running.

Check the active context and cluster connection:

```bash
kubectl config current-context
kubectl cluster-info
```

## 6. Verify Installed Software Versions

```bash
docker --version
kubectl version --client
kind version
helm version --short
```

> **Note:** The download URLs above target `linux/amd64`, and the kind command pins version `v0.22.0`. Use matching binaries if your CPU architecture differs.

