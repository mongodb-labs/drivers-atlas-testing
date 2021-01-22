.. _test-scenario-format-specification:

Atlas Planned Maintenance Test Scenario Format
==============================================

.. note:: Detailed information about terms that are italicized in this document can be found in the
   :ref:`terms-technical-design` section.

The YAML file format described herein is used to define platform-independent *Atlas Planned Maintenance Tests* in
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

  * testFailover: trigger an election in the cluste rusing the "test failover"
    API endpoint. The value MUST be ``true``.
    
    testFailover SHOULD be followed by sleep and waitForIdle operations
    because it does not update maintenance state synchronously (see
    `PRODTRUAGE-1232 <https://jira.mongodb.org/browse/PRODTRIAGE-1232>`_).

    Example::
    
      testFailover: true

  * restartVms: perform a rolling restart of all nodes in the cluster.
    This operation requires Atlas Global Operator API key to be set when
    invoking ``astrolabe``. The value MUST be ``true``.

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

    Example::

      waitForIdle: true

* uriOptions (document): Document containing ``key: value`` pairs of URI options that must be included in the
  connection string passed to the workload executor by the *Test Orchestrator*.

* driverWorkload (document): Description of the driver workload to execute
  The document must be a complete test as defined by the
  `Unified Test Format specification <https://github.com/mongodb/specifications/blob/master/source/unified-test-format/unified-test-format.rst>`_.
  
  Note that the ``initialData`` (and, by necessity, ``createEntities``)
  field of this document is interpreted and executed by ``astrolabe``, while
  the remaining fields are interpreted and executed by the workload executor.

-------
Changes
-------

* 2020-04-22: Move the test format specification into a separate file.
