Atlas Planned Maintenance Tests
===============================

The YAML files in this directory are platform-independent tests that ``astrolabe`` can use to prove that drivers
behave as expected when running against Atlas clusters that are undergoing maintenance. See the
`Test Format Specification <https://mongodb-labs.github.io/drivers-atlas-testing/spec-test-format.html>`_ for a
detailed description of the test format.

Test File Naming Convention
---------------------------

The names of test files serve as the names of the tests themselves (as displayed in the Evergreen UI).
Consequently, it is recommended that file names observe the following naming convention::

  <DriverWorkloadName>-<MaintenancePlanName>.yaml

Use of ``camelCase`` is recommended for specifying the driver workload and maintenance plan names. Ideally, these
names should be descriptive enough to be self-explanatory though this might not be possible for more complex workloads
and maintenance plans.
