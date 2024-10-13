#!/usr/bin/env bash
set -o xtrace

"$PYTHON_BINARY" --version
"$PYTHON_BINARY" -m virtualenv "$PYMONGO_VIRTUALENV_NAME"
"$PYMONGO_VIRTUALENV_NAME/$PYTHON_BIN_DIR/pip" install -e mongo-python-driver
