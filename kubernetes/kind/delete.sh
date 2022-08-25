#!/bin/bash
set -o xtrace
set -e

# This script deletes all Kind clusters.

# Checks if the binary is available in the system PATH.
is_binary_available() {
  type "$1" >/dev/null 2>/dev/null
}

is_binary_available kind || (echo "Failed to find 'kind' binary in the system PATH" && exit 1)

kind delete cluster
