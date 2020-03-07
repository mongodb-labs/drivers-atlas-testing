#!/bin/sh
set -o xtrace  # Exit the script with error if any of the commands fail

# Install astrolabe in its own virtualenv
"$ASTROLABE_PY3_BINARY" -m virtualenv "$ASTROLABE_VIRTUALENV_NAME"
. "$ASTROLABE_VIRTUALENV_NAME"/bin/activate
pip install -e .

# Check that the installation worked and that we can talk to Atlas.
"$ASTROLABE_BINARY" check-connection
