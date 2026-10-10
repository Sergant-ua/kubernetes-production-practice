# Environment Setup Guide (WSL 2 + Docker + kind)

Quick reference guide for setting up the local working environment.

## 1. WSL 2 (Ubuntu)
Open PowerShell as Administrator:
```powershell
wsl --install
```
Restart your PC, launch Ubuntu, and update packages:
```bash
sudo apt update && sudo apt upgrade -y
```

## 2. Docker Engine
Install Docker inside WSL 2:
```bash
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io
sudo usermod -aG docker $USER
```
*(Restart your WSL terminal after this step).*

## 3. kubectl & kind
Install `kubectl`:
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
```
Install `kind`:
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.24.0/linux-amd64
chmod +x ./kind && sudo mv kind /usr/local/bin/kind
```

## 4. Cluster Creation
Create the `k8s-security` cluster:
```bash
cat <<EOT > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: k8s-security
nodes:
- role: control-plane
EOT

kind create cluster --config kind-config.yaml
kind export kubeconfig --name k8s-security
```
