#!/usr/bin/env bash
set -o xtrace
set -e

# This script creates a Kind cluster, installs the MongoDB Community Kubernetes Operator, and starts
# a 3-node MongoDB replicaset.

SCRIPT_DIR="$(dirname "$0")"

# Checks if the binary is available in the system PATH.
is_binary_available() {
  type "$1" >/dev/null 2>/dev/null
}

# Check for the expected CLI tools in the system PATH.
is_binary_available kind || (echo "Failed to find 'kind' binary in the system PATH" && exit 1)
is_binary_available helm || (echo "Failed to find 'helm' binary in the system PATH" && exit 1)
is_binary_available kubectl || (echo "Failed to find 'kubectl' binary in the system PATH" && exit 1)
is_binary_available cmctl || (echo "Failed to find 'cmctl' binary in the system PATH" && exit 1)
is_binary_available mongosh || (echo "Failed to find 'mongosh' binary in the system PATH" && exit 1)
is_binary_available jq || (echo "Failed to find jq 'binary' in the system PATH" && exit 1)

# Create local Kind cluster with specific host-port mapping. Wait for up to 5 minutes.
kind create cluster --config $SCRIPT_DIR/kind.yml --wait 5m

# Add helm repositories for the MongoDB Community Kubernetes Operator and the Cert Manager Operator.
helm repo add mongodb https://mongodb.github.io/helm-charts
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Install the MongoDB Community Kubernetes Operator.
helm install \
    community-operator mongodb/community-operator \
    --namespace default \
    --version v0.7.4

# Install cert-manager for generating TLS certificates.
kubectl create namespace cert-manager
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install \
    cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --version v1.9.0 \
    --set installCRDs=true

# Wait up to 2 minutes for the cert-manager API to be ready.
cmctl --namespace cert-manager check api --wait=2m

# Create the necessary configmap and TLS secret for Cert Manager to generate a new TLS certificate
# for our MongoDB servers and clients.
kubectl --namespace default create configmap ca-config-map --from-file=ca.crt=$SCRIPT_DIR/rootCA.pem
kubectl --namespace default create secret tls ca-key-pair  --cert=$SCRIPT_DIR/rootCA.pem  --key=$SCRIPT_DIR/rootCA-key.pem

# Create the Cert Manager certificate issuer and certificate
kubectl --namespace default apply -f $SCRIPT_DIR/cert-manager-issuer.yml
kubectl --namespace default apply -f $SCRIPT_DIR/cert-manager-certificate.yml

# Create the MongoDB 3-node replicaset.
kubectl --namespace default apply -f $SCRIPT_DIR/mongodb.yml

# Wait up to 10 minutes for the MongoDB replicaset to be in phase "Running". Sleep for 10 seconds
# before trying to wait because sometimes the "status" key isn't part of the resource definition
# immediately after creation.
sleep 10
kubectl --namespace default wait MongoDBCommunity/mongodb \
    --for=jsonpath='{.status.phase}'=Running \
    --timeout=10m

# Download the TLS certificate and key from the TLS secret created by Cert Manager. Decode them with
# jq and concatenate them together to match the format expected by MongoDB drivers.
kubectl --namespace default get secret mongodb-tls -o json | \
    jq -r '.data."tls.crt", .data."tls.key" | @base64d' > mongodb_tls_cert.pem

# After the MongoDB cluster transitions to the "Running" phase, the MongoDB Kubernetes Operator may
# still not have added the user specified in the service definition. Try to connect and run an
# authenticated command (show dbs) with the expected userinfo in a loop until it succeeds.
CONN_STRING="mongodb://user:12345@localhost:31181,localhost:31182,localhost:31183/admin?tls=true&tlsCertificateKeyFile=mongodb_tls_cert.pem&tlsCAFile=$SCRIPT_DIR/rootCA.pem"
until mongosh $CONN_STRING --eval "show dbs;"
do
    echo "Waiting 5 seconds for the user to be created..."
    sleep 5
done

echo "Kind cluster is ready!"
