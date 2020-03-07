#!/bin/sh
set -o xtrace  # Exit the script with error if any of the commands fail

$PYTHON_BINARY -m virtualenv pymongotestvenv
. pymongotestvenv/bin/activate
pip install -e .[srv]

$ASTROLABE --log-level debug spec-tests run temp-tests/ -e .evergreen/python/workload-executor.sh  --group-name testproject --cluster-name-salt somesalt
