#!/usr/bin/env bash
# ==============================================================================
# Generate Self-Signed TLS Certificates for Nginx Reverse Proxy
# ==============================================================================
set -euo pipefail

CERTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../nginx/certs" && pwd)"
mkdir -p "$CERTS_DIR"

if command -v openssl &> /dev/null; then
    echo "Generating TLS certificates using OpenSSL..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERTS_DIR/server.key" \
        -out "$CERTS_DIR/server.crt" \
        -subj "/C=US/ST=State/L=City/O=Hospital Platform/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
    echo "Certificates created in $CERTS_DIR"
else
    echo "OpenSSL not found. Falling back to python generator..."
    python3 scripts/generate_certs.py "$CERTS_DIR"
fi

