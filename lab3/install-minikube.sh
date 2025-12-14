#!/usr/bin/env bash
set -euo pipefail

# Installs kubectl + minikube into ./bin (relative to this script location)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$ROOT_DIR/bin"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "Unsupported arch: $ARCH"; exit 1 ;;
esac

mkdir -p "$BIN_DIR"

echo "Installing kubectl..."
curl -fsSL -o "$BIN_DIR/kubectl" "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/${OS}/${ARCH}/kubectl"
chmod +x "$BIN_DIR/kubectl"

echo "Installing minikube..."
curl -fsSL -o "$BIN_DIR/minikube" "https://storage.googleapis.com/minikube/releases/latest/minikube-${OS}-${ARCH}"
chmod +x "$BIN_DIR/minikube"

echo
echo "Done."
echo "Binaries installed to: $BIN_DIR"
echo "Try:"
echo "  $BIN_DIR/kubectl version --client"
echo "  $BIN_DIR/minikube version"
