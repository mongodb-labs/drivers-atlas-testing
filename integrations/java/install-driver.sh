#!/bin/bash

set -o errexit

cd mongo-java-driver || exit

./gradlew --info driver-workload-executor:compileJava
