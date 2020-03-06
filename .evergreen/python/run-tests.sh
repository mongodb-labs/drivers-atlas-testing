#!/bin/sh
set -o errexit  # Exit the script with error if any of the commands fail

$PYTHON_BINARY -m virtualenv astrolabevenv
. astrolabevenv/bin/activate
pip install -e .
ASTROLABE="$(pwd)/astrolabevenv/bin/astrolabe"

$PYTHON_BINARY -m virtualenv pymongotestvenv
git clone --branch 3.10.1 https://github.com/mongodb/mongo-python-driver.git
. pymongotestvenv/bin/activate
pip install -e mongo-python-driver/[srv]

$ASTROLABE --log-level debug spec-tests run temp-tests/ -e .evergreen/python/workload-executor.sh  --group-name testproject --cluster-name-salt somesalt
