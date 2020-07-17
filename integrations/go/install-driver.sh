#!/bin/bash

set -ex

echo "INSTALLING DRIVER"
cd integrations/$DRIVER_DIRNAME

export PATH=$GOROOT/bin:$PATH

go get go.mongodb.org/mongo-driver@master
go build -o executor workload-executor.go
