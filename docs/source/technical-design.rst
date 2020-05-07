Technical Design: Testing Drivers Against Atlas Planned Maintenance
===================================================================

.. attention:: This document is **not** updated regularly. It's only purpose is to provide the reader with information
   about design choices and decisions made during the conception and initial implementation of the ``astrolabe``
   framework. For up-to-date information on how to use ``astrolabe``, please see the :ref:`integration-guide`.


:Title: Testing Drivers against Atlas Planned Maintenance
:Author: Prashant Mital
:Lead: Matt Broadstone
:Advisors: Andrew Davidson, Sheeri Cabral, Will Shulman, Jeremy Mikola, Ian Whalen, Rachelle Palmer
:Status: Approved
:Type: Process
:Minimum Server Version: N/A
:Last Modified: January 28, 2020

--------
Abstract
--------

Testing drivers against Atlas clusters undergoing maintenance is required to increase the likelihood that deviations
of driver behavior from the high-availability and/or graceful-failure characteristics promised by `driver
specifications <https://github.com/mongodb/specifications>`_ are detected and rectified during development.
This specification outlines a testing framework that streamlines the process of testing drivers against Atlas clusters
undergoing maintenance thereby ensuring expeditious incorporation of this additional testing into all driver projects.
The improved test coverage will result in a superior user experience as workload disruption during planned maintenance
due to undiscovered bugs in the drivers, server or Atlas will become less likely.

-----------
Definitions
-----------

META
----

The keywords “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and
“OPTIONAL” in this document are to be interpreted as described in `RFC 2119 <https://www.ietf.org/rfc/rfc2119.txt>`_.

.. _terms-technical-design:

Terms
-----

Atlas Cluster
  Subordinate of an *Atlas Project* in Atlas’ Organizations and Projects hierarchy [#f1]_, an Atlas Cluster is a set of
  nodes comprising a MongoDB deployment.

Atlas Project
  Subordinate of an *Atlas Organization* in Atlas’ Organizations and Projects hierarchy [#f1]_. Each Atlas Organization
  can contain multiple Atlas Projects.

Atlas Organization
  The top-level entity in Atlas’ Organizations and Projects hierarchy [#f1]_.

Atlas Planned Maintenance Test
  An integration test that involves running a *Driver Workload* using a MongoDB Driver against an *Atlas Cluster* that
  is in the midst of applying a *Planned Maintenance Scenario*.

Cluster Configuration Options
  Umbrella term used to refer to all parameters that can be used to configure an *Atlas Cluster* via the *Atlas API*.
  There are two kinds of cluster configuration options - *Basic Configuration Options* and *Advanced Configuration Options*.

Basic Configuration Options
  Set of cluster configuration parameters that can be used to create a new *Atlas Cluster* via the Create One Cluster [#f2]_ endpoint,
  or that can be applied to an existing cluster via the Modify One Cluster [#f3]_ endpoint.

Advanced Configuration Options
  Set of cluster configuration parameters that be applied to an existing *Atlas Cluster* via the
  Modify Advanced Configuration Options for One Cluster [#f4]_ endpoint.

Cluster State
  The state of an *Atlas Cluster* as advertised by the “stateName” field in the response of the
  Get One Cluster [#f5]_ endpoint.

Test Scenario File
  A file containing a language and driver-agnostic description of a single *Atlas Planned Maintenance Test*.
  Each file specifies a *Planned Maintenance Scenario* and the associated *Driver Workload*.

Planned Maintenance Scenario
  Description of a plan to modify the *Cluster Configuration Options* of a running *Atlas Cluster*.
  A maintenance plan is described fully by an associated set of initial and final *Cluster Configuration Options*.

Driver Workload
  A language-agnostic description of MongoDB driver operations.

Workload Executor
  A user-implemented, driver-specific script responsible for parsing a *Driver Workload* and translating it into
  actual driver operations that are run against the test cluster.

Test Orchestrator
  User-facing command-line utility that accepts a *Workload Executor* and a *Test Scenario File* and runs an *Atlas Planned Maintenance Test*.

Atlas API
  `REST API <https://docs.atlas.mongodb.com/api/>`_ that provides programmatic access to MongoDB Atlas.

.. _astrolabe-architecture:

---------------------
Architecture Overview
---------------------

To ensure maintainability and extensibility, the Atlas Planned Maintenance Testing Framework has a modular design
comprised of the following components:

#. Test Scenario Format: the test format creates a standard language for describing Atlas Planned Maintenance Tests.
#. Workload Executor: a user-implemented, driver-specific script with a standard command-line API that translates driver
   workloads described in the test scenario format into driver operations that are run against the test cluster.
#. Test Orchestrator: a command-line utility that accepts Workload Executor and test specification in the
   Test Scenario Format and runs an Atlas Planned Maintenance Test. The Test Orchestrator is also responsible for
   leveraging the Atlas API to provision, configure, and monitor Atlas clusters.

.. figure:: static/specification-schematic.png
   :figwidth: 100%

   Schematic representation of the test framework architecture.

The subsequent sections describe each of these components in greater detail and are intended as a reference for
implementation of the testing framework described in this specification. Drivers MUST integrate this testing framework
into their continuous integration workflow - see the :ref:`integration-guide` for instructions.

--------------------
Test Scenario Format
--------------------

.. attention:: This section has been moved to :ref:`test-scenario-format-specification`.

-----------------
Workload Executor
-----------------

.. attention:: This section has been moved to :ref:`workload-executor-specification`.

-----------------
Test Orchestrator
-----------------

.. attention:: ``astrolabe`` is the reference implementation of the Test Orchestrator design described in this section.
   As ``astrolabe`` evolves to better serve the testing objectives of MongoDB Drivers and MongoDB Atlas, this section
   is likely to become outdated. Instead, readers are encouraged to study ``astrolabe``'s documentation and source
   code to gain an up-to-date understanding of the Test Orchestrator's implementation.

The Test Orchestrator is a command-line utility that ingests a Atlas Planned Maintenance Test specified in the
Test Scenario Format and leverages the Atlas API and a user-supplied Workload Executor to run the test on a live
Atlas Cluster.

Features
--------

The Test Orchestrator MUST support the following, low-level operations via the MongoDB Atlas API:

#. Creating a new Atlas Cluster with the given Cluster Configuration Options [#f2]_.
#. Adding a given IP address to the IP whitelist of an Atlas Project [#f6]_.
#. Creating a new database user with the given name and password on an Atlas Cluster [#f7]_.
#. Modifying the Cluster Configuration Options of a given, already running Atlas Cluster [#f3]_, [#f4]_.
#. Retrieving the server logs from all hosts in an Atlas Cluster [#f8]_.
#. Retrieving the Cluster State of a given Atlas Cluster.

To prevent leaking MongoDB Atlas API credentials from the test machines, the Test Orchestrator MUST support
the specification of API credentials via environment variables.

User-Facing API
---------------

The Test Orchestrator MUST be an executable that supports the following invocation pattern::

	./test-orchestrator spec-tests run-one path/to/workload-spec.yaml -e path/to/workload-executor

where:

* ``test-orchestrator`` is the Test Orchestrator executable,
* ``spec-tests run-one`` is the name of the command issued to this executable,
* ``path/to/workload-spec.yaml`` is the path to a test scenario file,
* ``-e`` is a flag indicating that the following argument is the workload executor binary, and
* ``path/to/workload-executor`` is the path to the workload executor binary that is to be used to run the Driver Workload.

Pseudocode Implementation
-------------------------

The pseudocode implementation in this section is provided for illustrative purposes only. For the sake of simplicity,
all interaction with the Atlas API in this sample implementation is handled by the ``AtlasController`` class which
implements the following interface::

    interface AtlasController {
        # Creates a new Atlas cluster from the "initial" Cluster Configuration Options of the given maintenanceScenario.
        # Returns the cluster's connection string.
        public createNewCluster(maintenanceScenario: object): string;

        # Initiates application of the "final" Cluster Configuration Options of the given maintenanceScenario.
        public triggerMaintenance(maintenanceScenario: object): void;

        # Blocks until the Cluster State becomes IDLE. Implementations MUST poll the API to monitor the Cluster State.
        # Implementations MUST account for rate limits on Atlas API resources and retry requests that fail
        # with a "429 Too Many Requests" response code.
        public waitUntilClusterIdle(): void;

        # Fetches the server (mongod & mongos) logs from the Atlas Cluster nodes and writes them to disk.
        public writeServerLogs(): void;
    }

Then, the Test Orchestrator can be implemented as follows::

    # Import the atlas controller.
    import { AtlasAPI } from "atlasController"

    # The testOrchestrator function accepts the path to a scenario YAML file
    # and the path to the workload executor executable. This function will be invoked with arguments
    # parsed from the command-line invocation of the test orchestrator binary.
    function testOrchestrator(scenarioFile: string, workloadExecutorPath: string): void {

        # Initialize Atlas controller.
        const atlasController = AtlasController();

        # Parse the maintenance scenario and the driver workload from the file.
        maintenanceScenario, driverWorkload = parseScenario(scenarioFile);

        # Create a cluster and wait for it to be ready for running operations.
        connectionString = atlasController.createNewCluster(maintenanceScenario);
        atlasController.waitUntilClusterIdle();

        # Initiate the driver workload in a subprocess.
        workloadSubprocess = spawnProcess([workloadExecutorPath, connectionString, driverWorkload]);

        # Implement maintenance plan and wait for completion.
        atlasController.triggerMaintenance(maintenanceScenario);
        atlasController.waitUntilClusterIdle();

        # Send a SIGINT to the workload executor to terminate workloads that run indefinitely.
        workloadSubprocess.send(SIGINT);

        # Write the contents of the workload executor's standard streams (stdout and stderr) to file for debugging use.
        writeWorkloadExecutorLogs(workloadSubprocess)

        # Fetch Atlas logs and write them to disk.
        atlasController.writeServerLogs();

        # The test orchestrator SHOULD output one test result file per scenario file in the standard
        # XUnit XML Format. This will enable the elegant test status console on Evergreen.
        # The XUnit output MAY use the workload statistics returned by the executor to make this output more informative.
        writeJUnitEntry(workloadSubprocess);

        # The test orchestrator sets the same exit-code as the workload executor to indicate test success/failure.
        process.exit(workloadSubprocess.exitCode);
    }


.. rubric:: Footnotes

.. [#f1] See https://docs.atlas.mongodb.com/organizations-projects/ for details about the Organizations and Projects hierarchy in MongoDB Atlas.
.. [#f2] Create One Cluster endpoint: https://docs.atlas.mongodb.com/reference/api/clusters-create-one/
.. [#f3] Modify One Cluster endpoint: https://docs.atlas.mongodb.com/reference/api/clusters-modify-one/
.. [#f4] Modify Advanced Configuration Options for One Cluster endpoint: https://docs.atlas.mongodb.com/reference/api/clusters-modify-advanced-configuration-options/
.. [#f5] Get One Cluster endpoint: https://docs.atlas.mongodb.com/reference/api/clusters-get-one/
.. [#f6] Add Entries to IP Whitelist endpoint: https://docs.atlas.mongodb.com/reference/api/whitelist-add-one/
.. [#f7] Create Database User endpoint: https://docs.atlas.mongodb.com/reference/api/database-users-create-a-user/
.. [#f8] Logs endpoint: https://docs.atlas.mongodb.com/reference/api/logs/