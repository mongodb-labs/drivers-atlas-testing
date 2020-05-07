.. _test-scenario-format-specification:

Atlas Planned Maintenance Test Scenario Format
==============================================

.. note:: Detailed information about terms that are italicized in this document can be found in the
   :ref:`terms-technical-design` section.

The YAML file format described herein is used to define platform-independent *Atlas Planned Maintenance Tests* in
YAML-formatted *Test Scenario Files*. Each Test Scenario File describes exactly one Atlas Planned Maintenance Test.
A Test Scenario File has the following keys:

* maintenancePlan (document): a *Planned Maintenance Scenario* object. Each object has the following keys:

  * initialConfiguration (document): Description of *Cluster Configuration Options* to be used for initializing the
    test cluster. This document MUST contain the following keys:

    * clusterConfiguration (document): Document containing initial *Basic Configuration Options* values.
      This document MUST, at a minimum, have all fields **required** by the
      `Create One Cluster <https://docs.atlas.mongodb.com/reference/api/clusters-create-one/>`_ endpoint.
    * processArgs (document): Document containing initial *Advanced Configuration Option* values. This MAY be an empty
      document if the maintenance plan does not require modifying the Advanced Configuration Options.

  * finalConfiguration (document): Description of **new** *Cluster Configuration Options* to be applied to the
    test cluster. This document MUST contain the following keys (note that at least one of these fields MUST be
    a non-empty document):

    * clusterConfiguration (document): Document containing final *Basic Configuration Option* values.
      This MAY be an empty document if no changes to the Basic Configuration Options are needed by the maintenance plan.
      If non-empty, this document MUST, at a minimum, have all fields **required** by the
      `Modify One Cluster <https://docs.atlas.mongodb.com/reference/api/clusters-modify-one/>`_ endpoint.
    * processArgs (document): Document containing final *Advanced Configuration Option* values.
      This MAY be an empty document if the maintenance plan does not require modifying the Advanced Configuration Options.

  * uriOptions (document): Document containing ``key: value`` pairs of URI options that must be included in the
    connection string passed to the workload executor by the *Test Orchestrator*.

* driverWorkload (document): Object describing a *Driver Workload*. Has the following keys:

  * collection (string): Name of the collection to use for running test operations.
  * database (string): Name of the database to use for running test operations.
  * testData (array, optional): Array of documents to be inserted into the ``database.collection`` namespace before
    starting the test run. Test data insertion is performed by the *Test Orchestrator* and this field MUST be ignored
    by the *Workload Executor*.
  * operations (array): Array of Operation objects, each describing an operation to be executed. The operations are run
    sequentially and repeatedly until the maintenance completes. Each object has the following keys:

    * object (string): The entity on which to perform the operation. Can be "database" or "collection".
    * name (string): name of the operation.
    * arguments (document): the names and values of arguments to be passed to the operation.
    * result (optional, multiple types): The result of executing the operation. This will correspond to the operation's
      return value.

-------
Changes
-------

* 2020-04-22: Move the test format specification into a separate file.
