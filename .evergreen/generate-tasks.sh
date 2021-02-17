#!/bin/sh

# Use this script to generate the task list for config.yml.

for f in tests/*.yml; do
  task=`basename $f |sed -e s/.yml//`
  
cat <<-EOT
  - name: $task
    cron: '@weekly'
    tags: ["all"]
    commands:
      - func: "run test"
        vars:
          TEST_NAME: $task
EOT

done
