#!/bin/sh
set -o errexit  # Exit the script with error if any of the commands fail

trap "exit 0" INT

"$PYMONGO_VIRTUALENV_NAME/$PYTHON_BIN_DIR/python.exe" ".evergreen/$DRIVER_DIRNAME/workload-executor.py" "$1" "$2"
