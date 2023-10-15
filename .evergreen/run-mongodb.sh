#!/bin/sh
set -o xtrace

# User configurable-options
# Each distro in the download script has a latest download.
export MONGODB_VERSION="latest"
export TOPOLOGY="server"

# Setup variables
export DRIVERS_TOOLS="$(dirname $(pwd))/drivers-tools"
if [ "Windows_NT" = "$OS" ]; then
   export DRIVERS_TOOLS=$(cygpath -m $DRIVERS_TOOLS)
fi
export MONGODB_BINARIES="$DRIVERS_TOOLS/mongodb/bin"
export MONGO_ORCHESTRATION_HOME="$DRIVERS_TOOLS/.evergreen/orchestration"
export PATH="$MONGODB_BINARIES:$PATH"

# Clone drivers-evergreen-tools
git clone --recursive https://github.com/mongodb-labs/drivers-evergreen-tools.git $DRIVERS_TOOLS

# Configure mongo-orchestration
echo "{ \"releases\": { \"default\": \"$MONGODB_BINARIES\" }}" > $MONGO_ORCHESTRATION_HOME/orchestration.config

# Fix absolute paths
for filename in $(find ${DRIVERS_TOOLS} -name \*.json); do
  perl -p -i -e "s|ABSOLUTE_PATH_REPLACEMENT_TOKEN|${DRIVERS_TOOLS}|g" $filename
done

# Make files executable
for i in $(find ${DRIVERS_TOOLS}/.evergreen -name \*.sh); do
  chmod +x $i
done

# Run mongo-orchestration
sh $DRIVERS_TOOLS/.evergreen/run-orchestration.sh
