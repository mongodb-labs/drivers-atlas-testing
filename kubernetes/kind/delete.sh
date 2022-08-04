#!/bin/bash
set -o xtrace
set -e

# This script deletes all Kind clusters.

# Checks if the binary is available, either in $PATH or at the explicit path provided.
is_binary_available() {
  type "$1" >/dev/null 2>/dev/null
}

# Allow overriding the kind binary path.
KIND=${KIND:-kind}
is_binary_available $KIND || (echo "Failed to find kind binary at '$KIND'" && exit 1)

$KIND delete cluster
