#!/bin/sh
set -o xtrace  # Exit the script with error if any of the commands fail

$PYTHON_BINARY -m virtualenv pymongotestvenv
. pymongotestvenv/bin/activate
pip install -e .[srv]

