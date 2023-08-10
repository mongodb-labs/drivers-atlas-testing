#! /bin/bash

# set -o xtrace   # Write all commands first to stderr
set -o errexit  # Exit the script with error if any of the commands fail

export PROJECT_DIRECTORY="$(pwd)/node-mongodb-native"
export NODE_LTS_VERSION="$NODE_LTS_VERSION"

ls -la
cd ${PROJECT_DIRECTORY}
ls -la
. .evergreen/install-dependencies.sh
