#!/bin/sh
set -o xtrace  # Exit the script with error if any of the commands fail

"$PYTHON_BINARY" -m virtualenv "$PYMONGO_VIRTUALENV_NAME"
"$PYMONGO_VIRTUALENV_NAME/bin/pip" install -e .[srv]

