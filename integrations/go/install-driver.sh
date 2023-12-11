#!/bin/bash

set -ex

echo "INSTALLING DRIVER"
cd integrations/$DRIVER_DIRNAME

export PATH=$GOROOT/bin:$PATH

go get go.mongodb.org/mongo-driver@v1
go mod tidy
go test -c workload_executor_test.go -o executor
