#!/bin/bash

set -ex

echo "INSTALLING DRIVER"
pwd
cd integrations/$DRIVER_DIRNAME
pwd

export PATH=$GOROOT/bin:$PATH 
go version
go get go.mongodb.org/mongo-driver@master
go build -o executor workload-executor.go
