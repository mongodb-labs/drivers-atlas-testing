# Welcome to astrolabe's documentation!

**astrolabe** is a toolkit for testing MongoDB driver behavior during
common MongoDB cluster reconfiguration operations. It currently supports
testing MongoDB drivers during Atlas Planned Maintenance events and
Kubernetes container scheduling events.

## Documentation Overview

[installing-running-locally](./installing-running-locally.md)
Instructions for installing `astrolabe` and running tests from your
local machine.

[integration-guide](./integration-guide.md)
Instructions on how to use `astrolabe` to test your driver against
MongoDB Atlas clusters in Evergreen.

[spec-workload-executor](./spec-workload-executor.md)
Information about the workload executor script that drivers must
implement in order to use `astrolabe`.

[spec-test-format](./spec-test-format.md)
Information about the file format used to define Atlas Planned
Maintenance and Kubernetes tests.

[technical-design](./technical-design.md)
Background reading about this testing framework's architecture and
design methodology.

[faq](./faq.md)  
Answers to questions and issues that come up often.
