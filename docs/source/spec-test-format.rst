.. _atlas-test-scenario-format:

Atlas Planned Maintenance Test Scenario Format
==============================================

.. note:: Detailed information about terms that are italicized in this section can be found in the
   :ref:`terms-technical-design` section.

The YAML file format described in this section is used to define platform-independent *Atlas Planned Maintenance Tests* in
YAML-formatted *Test Scenario Files*. Each Test Scenario File describes exactly one Atlas Planned Maintenance Test.
A Test Scenario File has the following keys:

* initialConfiguration (document): Description of *Cluster Configuration Options* to be used for initializing the
  test cluster. This document MUST contain the following keys:

  * clusterConfiguration (document): Document containing initial *Basic Configuration Options* values.
    This document MUST, at a minimum, have all fields **required** by the
    `Create One Cluster <https://docs.atlas.mongodb.com/reference/api/clusters-create-one/>`_ endpoint.
  * processArgs (document): Document containing initial *Advanced Configuration Option* values. This MAY be an empty
    document if the maintenance plan does not require modifying the Advanced Configuration Options.

* operations (array): List of operations to be performed, representing the
  maintenance event. Each operation is a document containing one key which is
  the name of the operation. The possible operations are:
  
  * setClusterConfiguration: set the cluster configuration to the specified
    *Cluster Configuration Options* as defined in initialConfiguration.
    The value must be the *Cluster Configuration Options* which MUST contain
    the following keys (note that at least one of these fields MUST be
    a non-empty document):

    * clusterConfiguration (document): Document containing final *Basic Configuration Option* values.
      This MAY be an empty document if no changes to the Basic Configuration Options are needed by the maintenance plan.
      If non-empty, this document MUST, at a minimum, have all fields **required** by the
      `Modify One Cluster <https://docs.atlas.mongodb.com/reference/api/clusters-modify-one/>`_ endpoint.
    * processArgs (document): Document containing final *Advanced Configuration Option* values.
      This MAY be an empty document if the maintenance plan does not require modifying the Advanced Configuration Options.
      
    Example::
    
      setClusterConfiguration:
        clusterConfiguration:
          providerSettings:
            providerName: AWS
            regionName: US_WEST_1
            instanceSizeName: M10
        processArgs: {}

  * testFailover: trigger an election in the cluster using the "test failover"
    API endpoint. The value MUST be ``true``.
    
    The workload executor MUST ignore the value of this key, so that
    the value can be changed to a hash in the future to provide options
    to the operation.
    
    testFailover SHOULD be followed by sleep and waitForIdle operations
    because it does not update maintenance state synchronously (see
    `PRODTRIAGE-1232 <https://jira.mongodb.org/browse/PRODTRIAGE-1232>`_).

    Example::
    
      testFailover: true

  * restartVms: perform a rolling restart of all nodes in the cluster.
    This operation requires Atlas Global Operator API key to be set when
    invoking ``astrolabe``. The value MUST be ``true``.
    
    The workload executor MUST ignore the value of this key, so that
    the value can be changed to a hash in the future to provide options
    to the operation.

    testFailover SHOULD be followed by sleep and waitForIdle operations
    because it does not update maintenance state synchronously.

    Example::

      restartVms: true

  * assertPrimaryRegion: assert that the primary in the deployment is in the
    specified region. The value MUST be a hash with the following keys:
    
    * region (string, required): the region name as defined in Atlas API,
      e.g. ``US_WEST_1``.
    * timeout (floating-point number, optional): the maximum time, in
      seconds, to wait for the region to become the expected one.
      Default is 90 seconds.

    This operation is undefined and MUST NOT be used when the deployment is
    a sharded cluster.

    Example::
    
      assertPrimaryRegion:
        region: US_WEST_1
        timeout: 15
    
  * sleep: do nothing for the specified duration. The value MUST be the duration
    to sleep for, in seconds.

    Example::
    
      sleep: 10
    
  * waitForIdle: wait for cluster maintenance state to become "idle".
    The value MUST be ``true``.
    
    The workload executor MUST ignore the value of this key, so that
    the value can be changed to a hash in the future to provide options
    to the operation.

    Example::

      waitForIdle: true

  For all maintenance operations other than ``sleep``, after the maintenance
  operation is performed, ``astrolabe`` will wait for cluster state to become
  idle. When performing a VM restart in a sharded cluster, due to the state
  not being updated for a potentially long time, the test SHOULD add an
  explicit ``sleep`` operation for at least 30 seconds.

* driverWorkload (document): Description of the driver workload to execute
  The document must be a complete test as defined by the
  `Unified Test Format specification <https://github.com/mongodb/specifications/blob/master/source/unified-test-format/unified-test-format.rst>`_.
  
  The workload MUST use a single test, as defined in the unified test format
  specification.
  
  The workload MUST use the ``loop`` unified test format operation to
  define the MongoDB operations to execute during maintenance. There MUST
  be exactly one ``loop`` operation per scenario, and it SHOULD be the last
  operation in the scenario.

  The scenario MUST use ``storeErrorsAsEntity``, ``storeSuccessesAsEntity``,
  and ``storeIterationsAsEntity`` operation arguments to allow the workload
  executor to retrieve errors, failures, and operation and iteration counts for
  the executed workload. The entity names for these options MUST be as follows:

  - ``storeErrorsAsEntity``: ``errors``
  - ``storeSuccessesAsEntity``: ``successes``
  - ``storeIterationsAsEntity``: ``iterations``

  The scenario MUST NOT use ``storeFailuresAsEntity`` to ensure that all errors
  and failures are reported under a single ``errors`` entity irrespective of how
  a test runner might distinguish errors and failures (if at all). Note that
  some ValidateWorkloadExecutor tests may still use ``storeFailuresAsEntity``
  with the entity name ``failures`` to assert workload executor correctness.

  The scenario MUST use ``storeEventsAsEntities`` operation argument
  when defining MongoClients to record CMAP and command events published
  during maintenance. All events MUST be stored in an entity named ``events``.
  When this option is used, ``astrolabe`` will retrieve the collected events and
  store them as an Evergreen build artifact, and will also calculate statistics
  for command execution time and connection counts.

.. note:: A previous version of this document specified a top-level
  ``uriOptions`` for specifying URI options for the MongoClient under test.
  In the current version, options can be specified using the ``uriOptions``
  key of the unified test format when creating a client entity.


.. _kubernetes-test-scenario-format:

Kubernetes Test Scenario Format
===============================

Kubernetes Tests use two separate YAML document formats: the *Kubernetes Test
Scenario File* and the *Workload File*. The combination of one *Kubernetes Test
Scenario File* and one *Workload File* defines a unique Kubernetes Test. The
following sections describe the format for each type of document.

Kubernetes Test Scenario File
-----------------------------

A *Kubernetes Test Scenario File* describes a sequence of operations that modify
the running conditions or configuration of a MongoDB cluster running in
Kubernetes. A *Kubernetes Test Scenario File* has the following keys:

* operations (array): List of operations to be performed. The possible
  operations are:

  * ``kubectl``: Run a command using the `kubectl
    <https://kubernetes.io/docs/reference/kubectl/kubectl/>`_ command line tool.
    The value MUST be a valid array of arguments for the ``kubectl`` command line
    tool. Note that the ``kubectl`` executable must be in the system PATH.

    Example::

      kubectl: [--namespace, default, delete, pod, mongodb-0]

  * ``sleep``: Do nothing for the specified duration. The value MUST be the
    duration to sleep for, in seconds.

    Example::

      sleep: 10

Workload File
-------------

A *Workload File* describes a set of operations that the MongoDB driver under
test will run while connected to the MongoDB cluster in Kubernetes.

The document must be a complete test as defined by the `Unified Test Format
specification <https://github.com/mongodb/specifications/blob/master/source/unified-test-format/unified-test-format.rst>`_.

-------
Changes
-------

* 2020-04-22: Move the test format specification into a separate file.
* 2022-08-08: Add specification for Kubernetes tests.
