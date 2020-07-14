#!/bin/bash

set -ex

PATH=$GOROOT/bin:$PATH go build -o integrations/$DRIVER_DIRNAME/executor integrations/$DRIVER_DIRNAME/workload-executor.go