#! /bin/bash

# set -o xtrace   # Write all commands first to stderr
set -o errexit  # Exit the script with error if any of the commands fail

export PROJECT_DIRECTORY="$(pwd)/node-mongodb-native"
export NODE_LTS_VERSION="$NODE_LTS_VERSION"

cd ${PROJECT_DIRECTORY}
. .evergreen/install-dependencies.sh
