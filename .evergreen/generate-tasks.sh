#!/bin/sh

for f in tests/*.yaml; do
  task=`basename $f |sed -e s/.yaml//`
  
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
