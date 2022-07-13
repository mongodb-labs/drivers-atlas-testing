#!/bin/sh
set -o xtrace
set -e

# This script creates a Kind cluster, installs the MongoDB Community Kubernetes Operator, and starts
# a 3-node MongoDB replicaset.

SCRIPT_DIR="$(dirname "$0")"

# Checks if the binary is available, either in $PATH or at the explicit path provided.
is_binary_available() {
  type "$1" >/dev/null 2>/dev/null
}

# Allow overriding the kind, helm, kubectl, cmctl, and jq binary paths.
KIND=${KIND:-kind}
is_binary_available $KIND || (echo "Failed to find kind binary at '$KIND'" && exit 1)

HELM=${HELM:-helm}
is_binary_available $HELM || (echo "Failed to find helm binary at '$HELM'" && exit 1)

KUBECTL=${KUBECTL:-kubectl}
is_binary_available $KUBECTL || (echo "Failed to find kubectl binary at '$KUBECTL'" && exit 1)

CMCTL=${CMCTL:-cmctl}
is_binary_available $CMCTL || (echo "Failed to find cmctl binary at '$CMCTL'" && exit 1)

JQ=${JQ:-jq}
is_binary_available $JQ || (echo "Failed to find jq binary at '$JQ'" && exit 1)

# Create local Kind cluster with specific host-port mapping. Wait for up to 5 minutes.
$KIND create cluster --config $SCRIPT_DIR/kind.yml --wait 5m

# Add helm repositories for the MongoDB Community Kubernetes Operator and the Cert Manager Operator.
$HELM repo add mongodb https://mongodb.github.io/helm-charts
$HELM repo add jetstack https://charts.jetstack.io
$HELM repo update

# Install the MongoDB Community Kubernetes Operator.
$HELM install \
    community-operator mongodb/community-operator \
    --namespace default \
    --version v0.7.4

# Install cert-manager for generating TLS certificates.
$KUBECTL create namespace cert-manager
$HELM repo add jetstack https://charts.jetstack.io
$HELM repo update
$HELM install \
    cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --version v1.9.0 \
    --set installCRDs=true

# Wait up to 2 minutes for the cert-manager API to be ready.
$CMCTL --namespace cert-manager check api --wait=2m

# Create the necessary configmap and TLS secret for Cert Manager to generate a new TLS certificate
# for our MongoDB servers and clients.
$KUBECTL --namespace default create configmap ca-config-map --from-file=ca.crt=$SCRIPT_DIR/rootCA.pem
$KUBECTL --namespace default create secret tls ca-key-pair  --cert=$SCRIPT_DIR/rootCA.pem  --key=$SCRIPT_DIR/rootCA-key.pem

# Create the Cert Manager certificate issuer and certificate
$KUBECTL --namespace default apply -f $SCRIPT_DIR/cert-manager-issuer.yml
$KUBECTL --namespace default apply -f $SCRIPT_DIR/cert-manager-certificate.yml

# Create the MongoDB 3-node replicaset.
$KUBECTL --namespace default apply -f $SCRIPT_DIR/mongodb.yml

# Wait up to 10 minutes for the MongoDB replicaset to be in phase "Running". Sleep for 10 seconds
# before trying to wait because sometimes the "status" key isn't part of the resource definition
# immediately after creation.
sleep 10
$KUBECTL --namespace default wait MongoDBCommunity/mongodb \
    --for=jsonpath='{.status.phase}'=Running \
    --timeout=10m

# Download the TLS certificate and key from the TLS secret created by Cert Manager. Decode them with
# jq and concatenate them together to match the format expected by MongoDB drivers.
$KUBECTL --namespace default get secret mongodb-tls -o json | \
    $JQ -r '.data."tls.crt", .data."tls.key" | @base64d' > mongodb_tls_cert.pem

# Sleep for 30 seconds to allow the Kubernetes operator to add the user to the database.
# TODO: Find a better way to wait for the availability of the user than just sleeping.
sleep 30
