#!/bin/bash

set -o errexit

export JAVA_HOME="/opt/java/jdk17"

cd mongo-java-driver || exit
./gradlew --info driver-workload-executor:shadowJar
cd ..
cp mongo-java-driver/driver-workload-executor/build/libs/driver-workload-executor-*.jar driver-workload-executor.jar

