#!/bin/bash

set -o xtrace
set -o errexit

cd mongo-java-driver || exit
./gradlew --info driver-workload-executor:shadowJar
cd ..
cp mongo-java-driver/driver-workload-executor/build/libs/driver-workload-executor-*.jar driver-workload-executor.jar
