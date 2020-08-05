#!/bin/bash

set -o errexit

export JAVA_HOME="/opt/java/jdk11"

cd mongo-java-driver || exit

./gradlew --info driver-workload-executor:compileJava
