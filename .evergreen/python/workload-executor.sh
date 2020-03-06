#!/bin/sh
set -o errexit  # Exit the script with error if any of the commands fail

. pymongotestvenv/bin/activate
python "$(pwd)/.evergreen/python/workload-executor.py" "$1" "$2"
