Drivers Atlas Testing Architecture
==================================

The Drivers Atlas Testing project validates the behavior of drivers against
Atlas clusters. For example, a test could be to perform queries or writes
in a loop while Atlas performs a maintenance operation, and assert that all
queries and writes complete successfully.

The project consists of the following principal components:

- Astrolabe - the orchestration utility.
- :doc:`Workload executors <spec-workload-executor>` - wrappers providing
  a common interface to each driver's `unified test runner <https://github.com/mongodb/specifications/blob/master/source/unified-test-format/unified-test-format.rst>`_.
- Each driver's unified test runner.
- :doc:`The test scenario specification <spec-test-format>`.

Astrolabe
---------

Users invoke ``astrolabe`` to perform a test. Astrolabe interacts with Atlas
and it performs several common tasks to keep the workload executors as small
and simple as possible. Specifically, Astrolabe:

- Creates an Atlas cluster for testing.
- Launches a workflow executor pointed at the cluster.
- Initiates Atlas maintenance operations in accordance with the test scenario.
- Waits for all operations to complete.
- Requests termination of the workflow executor.
- Verifies the successful termination of the workflow executor
- Verifies that the workflow executor executed the workload.
- Retrieves Atlas logs and FTDC data for problem diagnosis.
- Calculates statistics and aggregates information obtained during the
  test run, for example it calculates the peak number of connections per
  server and average operation latency.
- Tears down the Atlas cluster.
- Uploads Atlas logs, event data produced by the workflow executor and
  aggregated statistics as Evergreen build artifacts.

Astrolabe is:

- Written in Python.
- Runs on Linux and Windows.
- Provides a CLI interface.
- Is the only component of Drivers Atlas Testing that communicates with the
  Atlas API.


Workload Executors
------------------

Each driver that is tested by Drivers Atlas Testing must implement a
:doc:`workload executor <spec-workload-executor>`,
which is a wrapper script that essentially provides a common
interface to the driver's unified test runner.

The workload executor is invoked by Astrolabe once a test Atlas cluster is
up and running. The workload executor:

- Instantiates the driver's unified test runner.
- Receives the workload specification, which is a unified test format test,
  from Astrolabe, and passes it to the unified test runner.
- Sets up a termination signal handler.
- Invokes the unified test runner to execute the workload, which ordinarily
  contains a `loop operation <https://github.com/mongodb/specifications/blob/master/source/unified-test-format/unified-test-format.rst#loop>`_.
- When the termination signal is received from Astrolabe, instructs the
  unified test runner to stop looping.
- Collects the number of iterations and successful operations performed by
  the test runner, the number of errorsr and failures, the events produced
  by the driver while executing the workload, and writes all of this
  to files.


Unified Test Runners
--------------------

On the driver side, the test workload is executed by the driver's
`unified test runner <https://github.com/mongodb/specifications/blob/master/source/unified-test-format/unified-test-format.rst>`_.
The workload definitions must be valid unified test format tests with
some additional constraints to simplify the implementation of Astrolabe
as well as workload executors.

The unified test format specification has been extended to provide several
special operations, most importantly the ``loop`` operation, and options
needed for Drivers Atlas Testing.


Test Scenario
-------------

The :doc:`test scenario <spec-test-format>` describes the test to be performed.
It consists of the following components:

- Initial Atlas cluster configuration. Used by Astrolabe when creating the
  cluster.
- Atlas maintenance operations to be performed. The operations are
  parsed and executed by Astrolabe.
- Driver workload to execute, which is a valid (and complete)
  unified test format test.

There are some additional requirements imposed by Drivers Atlas Testing on
the test scenarios to simplify the implementation of both Astrolabe and
the workload executors, namely:

- There must be exactly one ``loop`` operation per test scenario.
- The names of entities used for retrieving events and statistics are
  explicitly defined and fixed.


Results & Artifacts
-------------------

Each test run produces the following results and artifacts:

- Success or failure indication. Any errors or unified test runner failures
  encountered during the test run fails the test run.
- Execution log. This is useful for debugging but, because driver operations
  are performed in an infinite loop, is generally not useful for higher-level
  analysis of the impact of Atlas maintenance on applications.
- Server logs for all nodes in the cluster and FTDC data. Currently
  Drivers Atlas Testing does not use these logs but they are stored for
  troubleshooting or investigative purposes.
- Operation statistics: number of loop iterations performed, number of
  successful operations performed, number of errors and failures encountered.
- Connection statistics: peak number of connections per server.
- Execution statistics: average, 95th, 99th percentiles of operation
  execution times.

The aggregate statistics are calculated by the ``astrolabe`` tool.
When the test scenario is executed locally instead of in Evergreen, calculation
of some of the statistics and aggregates must be performed explicitly by
invoking ``astrolabe`` appropriately.


Evergreen
---------

While all of the tests can be :doc:`executed locally <installing-running-locally>`,
it is expected that most of the testing would be performed in Evergreen
across all drivers via periodic builds.

Additionally, Drivers Atlas Testing is intended to be used for ad-hoc testing
of particular maintenance scenarios, possibly scoped to particular drivers,
via Evergreen patch builds.
