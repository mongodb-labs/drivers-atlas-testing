#!/bin/sh

# Use this script to generate the Atlas test task list for config.yml.

for f in tests/atlas/*.yml; do
  task=`basename $f |sed -e s/.yml//`
  
cat <<-EOT
  - name: $task
    tags: ["all"]
    commands:
      - func: "run atlas test"
        vars:
          TEST_NAME: $task
          ATLAS: "true"
EOT

done
