#!/bin/bash -ex
# this file runs all of the tests for the workload executor
# you have to manually interrupt the tests with CTRL-C
for file in ../../../tests/*
do
   if [[ $file == *.yml ]]
   then
      echo $file
      python3 workload-executor.py "mongodb://user:password@localhost" "$file"
   fi
done
