#! /bin/bash

# set -o xtrace   # Write all commands first to stderr
set -o errexit  # Exit the script with error if any of the commands fail

export PROJECT_DIRECTORY="$(pwd)/node-mongodb-native"
export NODE_LTS_VERSION="$NODE_LTS_VERSION"
export NPM_VERSION=9

cd ${PROJECT_DIRECTORY}
source .evergreen/prepare-shell.sh
source .evergreen/install-dependencies.sh
