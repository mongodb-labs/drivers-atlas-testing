#!/usr/bin/env bash
set -o xtrace

if [ ! -f ./secrets-export.sh ]; then
  echo "Please run setup-secrets.sh first!"
fi
source ./secrets-export.sh

# User configurable-options
# Each distro in the download script has a latest download.
export MONGODB_VERSION=${MONGODB_VERSION:-rapid}
export TOPOLOGY="server"

# Setup variables
export MONGODB_BINARIES="$DRIVERS_TOOLS/mongodb/bin"
export MONGO_ORCHESTRATION_HOME="$DRIVERS_TOOLS/.evergreen/orchestration"
export PATH="$MONGODB_BINARIES:$PATH"

# Configure mongo-orchestration
$DRIVERS_TOOLS/.evergreen/setup.sh

# Run mongo-orchestration
$DRIVERS_TOOLS/.evergreen/run-orchestration.sh
