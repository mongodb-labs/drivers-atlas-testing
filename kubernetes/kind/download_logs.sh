#!/bin/bash
set -o xtrace
set -e

# This script downloads logs from all pods in the "default" Kubernetes namespace to a .log file with
# the same name as the pod (e.g. "mongodb-0.log").

# Checks if the binary is available, either in $PATH or at the explicit path provided.
is_binary_available() {
  type "$1" >/dev/null 2>/dev/null
}

KUBECTL=${KUBECTL:-kubectl}
is_binary_available $KUBECTL || (echo "Failed to find kubectl binary at '$KUBECTL'" && exit 1)

# For each pod in the default namespace, download the logs from all containers in the pod to a file
# named $pod.log.
for pod in $($KUBECTL --namespace default get pods --no-headers -o custom-columns=":metadata.name"); do
  $KUBECTL --namespace default logs --prefix --all-containers --ignore-errors $pod > $pod.log
  echo "Downloaded logs from pod $pod to $pod.log"
done
