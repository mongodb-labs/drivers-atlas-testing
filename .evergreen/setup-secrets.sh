#!/usr/bin/env bash
set -ex

export DRIVERS_TOOLS="$(dirname $(pwd))/drivers-tools"
if [ "Windows_NT" = "$OS" ]; then
   export DRIVERS_TOOLS=$(cygpath -m $DRIVERS_TOOLS)
fi

# Clone drivers-evergreen-tools
git clone https://github.com/mongodb-labs/drivers-evergreen-tools.git $DRIVERS_TOOLS

. $DRIVERS_TOOLS/.evergreen/secrets_handling/setup-secrets.sh drivers/astrolabe

echo "export DRIVERS_TOOLS=$DRIVERS_TOOLS" >> secrets-export.sh