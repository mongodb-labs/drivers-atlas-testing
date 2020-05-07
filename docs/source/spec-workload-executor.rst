.. _workload-executor-specification:

Workload Executor Specification
===============================

.. note:: Detailed information about terms that are italicized in this document can be found in the
   :ref:`terms-technical-design` section.

The *Workload Executor* is a script that translates a *Driver Workload* specified in a *Test Scenario File* into
driver operations that are run against a test cluster. This script MUST be implemented by every driver.
Workload Executors enable the reuse of ``astrolabe``'s test orchestration and cluster monitoring capabilities across
all drivers by providing an abstraction for translating *Driver Workloads* specified in the platform-agnostic
test format into native driver operations that are run against a live Atlas cluster.

User-Facing API
---------------

The Workload Executor MUST be a standalone executable that can be invoked as::

  $ path/to/workload-executor connection-string workload-spec

where:

* ``path/to/workload-executor`` is the path to the Workload Executor executable script,
* ``connection-string`` is ``mongodb+srv`` which may contain any of the
  `standardized URI options <https://github.com/mongodb/specifications/blob/master/source/uri-options/uri-options.rst>`_
  that is to be used to connect to the Atlas cluster, and
* ``workload-spec`` is a JSON blob representation of the ``driverWorkload`` field from the
  :ref:`test-scenario-format-specification`.

.. note:: Some languages might find it convenient to wrap their natively implemented workload executors in a shell
   script in order to conform to the user-facing API described here. See :ref:`wrapping-workload-executor-shell-script`
   for details.

Behavioral Description
----------------------

After accepting the inputs, the workload executor:

#. MUST use the input connection string to instantiate the ``MongoClient`` of the driver that is to be tested.
   Note that the workload executor:

   * MUST NOT override any of the URI options specified in the incoming connection string.
   * MUST NOT augment the incoming connection string with any additional URI options.

#. MUST parse the incoming the ``driverWorkload`` document and use the ``MongoClient`` instance from the previous step
   to run the operations described therein in accordance with the :ref:`test-scenario-format-specification`.
   Note that the workload executor:

   * MUST run operations sequentially and in the order in which they appear in the ``operations`` array.
   * MUST repeat the entire set of specified operations indefinitely, until the **termination signal** from
     ``astrolabe`` is received.
   * MUST keep count of the number of operations failures (``numFailures``) that are encountered while running
     operations. An operation failure is when the actual return value of an operation does not match its
     expected return value (as defined in the ``result`` field of the ``driverWorkload``).
   * MUST keep count of the number of operation errors (``numErrors``) that are encountered while running
     operations. An operation error is when running an operation unexpectedly raises an error. Workload executors
     implementations should try to be as resilient as possible to these kinds of operation errors.
   * MUST keep count of the number of operations that are run successfully (``numSuccesses``).

#. MUST set a signal handler for handling the termination signal that is sent by ``astrolabe``. The termination signal
   is used by ``astrolabe`` to communicate to the workload executor that it should stop running operations. Upon
   receiving the termination signal, the workload executor:

   * MUST stop running driver operations and exit soon.
   * MUST dump collected workload statistics as a JSON file named ``results.json`` in the current working directory
     (i.e. the directory from where the workload executor is being executed). Workload statistics MUST contain the
     following fields (drivers MAY report additional statistics using field names of their choice):

     * ``numErrors``: the number of operation errors that were encountered during the test.
     * ``numFailures``: the number of operation failures that were encountered during the test.
     * ``numSuccesses``: the number of operations executed successfully during the test.

   .. note:: The values of ``numErrors`` and ``numFailures`` are used by ``astrolabe`` to determine the overall
      success or failure of a driver workload execution. A non-zero value for either of these fields is construed
      as a sign that something went wrong while executing the workload and the test is marked as a failure.
      The workload executor's exit code is **not** used for determining success/failure and is ignored.

   .. note:: If ``astrolabe`` encounters an error in parsing the workload statistics dumped to ``results.json``
      (caused, for example, by malformed JSON), ``numErrors``, ``numFailures``, and ``numSuccesses``
      will be set to ``-1`` and the test run will be assumed to have failed.

   .. note:: The choice of termination signal used by ``astrolabe`` varies by platform. ``SIGINT`` [#f1]_ is used as
      the termination signal on Linux and OSX, while ``CTRL_BREAK_EVENT`` [#f2]_ is used on Windows.

   .. note:: On Windows systems, the workload executor is invoked via Cygwin Bash.


Pseudocode Implementation
-------------------------

.. code::

    # targetDriver is the driver to be tested.
    import { MongoClient } from "targetDriver"

    # The workloadRunner function accepts a connection string and a stringified JSON blob describing the driver workload.
    # This function will be invoked with arguments parsed from the command-line invocation of the workload executor script.
    function workloadRunner(connectionString: string, driverWorkload: object): void {

        # Use the MongoClient of the driver to be tested to connect to the Atlas Cluster.
        const client = MongoClient(connectionString);

        # Create objects which will be used to run operations.
        const db = client.db(driverWorkload.database);
        const collection = db.collection(driverWorkload.collection);

        # Initialize counters.
        var num_errors = 0;
        var num_failures = 0;
        var num_successes = 0;

        # Run the workload - operations are run sequentially, repeatedly until the termination signal is received.
        try {
            while (True) {
                for (let operation in workloadSpec.operations) {
                    try {
                        # The runOperation method runs operations as per the test format.
                        # The method return False if the actual return value of the operation does match the expected.
                        var was_succesful = runOperation(db, collection, operation);
                        if (was_successful) {
                            num_successes += 1;
                        } else {
                            num_errors += 1;
                        }
                    } catch (operationError) {
                        # We end up here if runOperation raises an unexpected error.
                        num_failures += 1;
                    }
                }
            }
        } catch (terminationSignal) {
            # The workloadExecutor MUST handle the termination signal gracefully.
            # The termination signal will be used by astrolabe to terminate drivers operations that otherwise run ad infinitum.
            # The workload statistics must be written to a file named results.json in the current working directory.
            fs.writeFile('results.json', JSON.stringify({‘numErrors’: num_errors, 'numFailures': num_failures, 'numSuccesses': num_successes}));
        }
    }

Reference Implementation
------------------------

`PyMongo's workload executor <https://github.com/mongodb-labs/drivers-atlas-testing/blob/master/integrations/python/pymongo/workload-executor>`_
serves as the reference implementation of the script described by this specification.


.. rubric:: Footnotes

.. [#f1] See http://man7.org/linux/man-pages/man7/signal.7.html for details about Linux signals
.. [#f2] See https://docs.microsoft.com/en-us/windows/console/ctrl-c-and-ctrl-break-signals for details about Windows
         console events
