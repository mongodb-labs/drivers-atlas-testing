Kubernetes Kind Tests
=====================

The YAML files in this directory are *Kubernetes Test Scenario Files* that are
intended to be run against a Kind cluster as configured by the configurations
and scripts in the ``kubernetes/kind`` directory. See the `Test Format
Specification <https://mongodb-labs.github.io/drivers-atlas-testing/spec-test-format.html>`_
for a detailed description of the test format.

Test File Naming Convention
---------------------------

The names of test file describes the tested scenario. Use of ``camelCase`` is recommended for test
files.