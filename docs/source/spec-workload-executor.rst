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

#. MUST use the input connection string to `instantiate the
   unified test runner <https://github.com/mongodb/specifications/blob/master/source/unified-test-format/unified-test-format.rst#id92>`_
   of the driver being tested. Note that the workload executor:

   * MUST NOT override any of the URI options specified in the incoming connection string.
   * MUST NOT augment the incoming connection string with any additional URI options.

#. MUST parse the incoming ``driverWorkload`` document and set up
    the driver's unified test runner to execute the provided workload.
    
    .. note::
    
      The workload SHOULD include a ``loop`` operation, as described in the
      unified test format, but the workload executor SHOULD NOT validate that
      this is the case.

#. MUST set a signal handler for handling the termination signal that is
   sent by ``astrolabe``. The termination signal is used by ``astrolabe``
   to communicate to the workload executor, and ultimately the unified test
   runner, that they should stop running operations.

#. MUST invoke the unified test runner to execute the workload.
   If the workload includes a ``loop`` operation, the workload will run until
   terminated by the workload executor; otherwise, the workload will terminate
   when the unified test runner finishes executing all of the operations.
   The workload executor MUST handle the case of a non-looping workload and
   it MUST terminate when the workload terminates.
   
   If the unified test runner raises an error while executing the workload,
   the error MUST be reported using the same format as errors handled by the
   unified test runner, as described in the unified test runner specification
   under the ``loop`` operation. Errors handled by the workload
   executor MUST be included in the calculated (and reported) error count.
   
   If the unified test runner reports a failure while executing the workload,
   the failure MUST be reported using the same format as failures handled by the
   unified test runner, as described in the unified test runner specification
   under the ``loop`` operation. Failures handled by the workload
   executor MUST be included in the calculated (and reported) failure count.
   If the driver's unified test runner is intended to handle all failures
   internally, failures that propagate out of the unified test runner MAY
   be treated as errors by the workload executor.

#. Upon receipt of the termination signal, MUST instruct the
   unified test runner to stop running the ``loop`` operation, if one
   is currently running. If the unified test runner is not currently running
   any ``loop`` operations, the workload executor MUST instruct the
   unified test runner to terminate when the next ``loop`` operation is
   encountered. The workload executor MAY attempt to terminate the
   unified test runner sooner (such as instructing the unified test runner
   to terminate after completing the current operation).
   The workload executor SHOULD terminate the unified test runner gracefully,
   such that in-progress operations are completed to their natural outcome
   (success or failure).

#. MUST wait for the unified test runner to terminate, either due to the
   receipt of the termination signal or due to completely executing all of
   the operations if they do not include loops.
   
#. MUST use the driver's unified test runner to retrieve the following
   entities from the entity map, if they are set:
   
   * iteration count: the number of iterations that the workload executor
     performed over the looped operations.
   
   * error lists: arrays of documents describing the errors that occurred
     while the workload executor was executing the operations. Each client
     entity may report errors to a separate error list, or the same
     error list may be used by multiple client entities.
   
   * failure lists: arrays of documents describing the failures that occurred
     while the workload executor was executing the operations. Each client
     entity may report errors to a separate failure list, or the same
     failure list may be used by multiple client entities.
   
   * event lists: arrays of documents describing the events that occurred
     while the workload executor was executing the operations. Each client
     entity may report events to a separate event list, or the same
     event list may be used by multiple client entities.

#. MUST calculate the aggregate counts of errors (``numErrors``) and failures
   (``numFailures``) from the error and failure lists.

#. MUST write the collected events, errors and failures into a JSON file named
   ``events.json`` in the current directory
   (i.e. the directory from where the workload executor is being executed). 
   The data written MUST be a map with the following fields:
   
   - For each event list entity, the name of the entity MUST become a key and the
     documents stored in the entity MUST become the respective value.
   
   - For each error list entity, the name of the entity MUST become a key and the
     documents stored in the entity MUST become the respective value.
   
   - The errors that the workload executor handles MUST be stored using the
     ``errors`` key.
   
   - For each failure list entity, the name of the entity MUST become a key and the
     documents stored in the entity MUST become the respective value.
   
   - The failures that the workload executor handles MUST be stored using the
     ``failures`` key.
         
#. MUST write the collected workload statistics into a JSON file named
   ``results.json`` in the current working directory (i.e. the directory
   from where the workload executor is being executed). Workload statistics
   MUST contain the following fields (drivers MAY report additional statistics
   using field names of their choice):

   * ``numErrors``: the number of operation errors that were encountered
     during the test. This includes errors handled by the workload executor
     and errors handled by the unified test runner.
   * ``numFailures``: the number of operation failures that were encountered
     during the test. This includes failures handled by the workload executor
     and failures handled by the unified test runner.
   * ``numSuccesses``: the number of successful loop iterations executed
     during the test.

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

    # The workloadRunner function accepts a connection string and a
    # stringified JSON blob describing the driver workload.
    # This function will be invoked with arguments parsed from the
    # command-line invocation of the workload executor script.
    function workloadRunner(connectionString: string, driverWorkload: object): void {

        # Use the driver's unified test runner to run the workload.
        const runner = UnifiedTestRunner(connectionString);
        
        try {
            runner.executeScenario();
        } catch (terminationSignal) {
            # The workloadExecutor MUST handle the termination signal gracefully.
            # The termination signal will be used by astrolabe to terminate drivers operations that otherwise run ad infinitum.
            # The workload statistics must be written to a file named results.json in the current working directory.
        }
        
        let results = {};
        let numSuccesses = runner.entityMap.get('iterationCount');
        let numErrors = 0;
        let numFailures = 0;
        for (name, events in runner.entityMap.get('events')) {
            results[name] ||= [];
            results[name].concat(events);
        }
        for (name, errors in runner.entityMap.get('errors')) {
            results[name] ||= [];
            results[name].concat(errors);
            numErrors += errors.length;
        }
        for (name, failures in runner.entityMap.get('failures')) {
            results[name] ||= [];
            results[name].concat(failures);
            numFailures += failures.length;
        }
        fs.writeFile('events.json', JSON.stringify(results);

        fs.writeFile('results.json', JSON.stringify({
            ‘numErrors’: numErrors,
            'numFailures': numFailures,
            'numSuccesses': numSuccesses,
        }));
    }

Reference Implementation
------------------------

`PyMongo's workload executor <https://github.com/mongodb-labs/drivers-atlas-testing/blob/master/integrations/python/pymongo/workload-executor>`_
serves as the reference implementation of the script described by this specification.


.. rubric:: Footnotes

.. [#f1] See http://man7.org/linux/man-pages/man7/signal.7.html for details about Linux signals
.. [#f2] See https://docs.microsoft.com/en-us/windows/console/ctrl-c-and-ctrl-break-signals for details about Windows
         console events
