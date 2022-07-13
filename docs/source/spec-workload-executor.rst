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
  :ref:`atlas-test-scenario-format`.

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

#. MUST initialize the following variables, which will later be used to generate
   the ``results.json`` and ``events.json`` output files:

   * ``events``: Empty array of objects.

   * ``errors``: Empty array of objects.

   * ``failures``: Empty array of objects.

   * ``numIterations``: Integer with value -1.

   * ``numSuccesses``: Integer with value -1.

   Note: ``numErrors`` and ``numFailures`` are intentionally omitted here as
   they will be derived directly from ``errors`` and ``failures``.

#. MUST invoke the unified test runner to execute the workload.
   If the workload includes a ``loop`` operation, the workload will run until
   terminated by the workload executor; otherwise, the workload will terminate
   when the unified test runner finishes executing all of the operations.
   The workload executor MUST handle the case of a non-looping workload and
   it MUST terminate if the unified test runner completely executes the
   specified workload.

   If the unified test runner raises an error while executing the workload,
   the error MUST be reported using the same format as errors handled by the
   unified test runner, as described in the unified test runner specification
   under the ``loop`` operation. The error MUST be appended to the ``errors``
   array.

   If the unified test runner reports a failure while executing the workload,
   the failure MUST be reported using the same format as failures handled by the
   unified test runner, as described in the unified test runner specification
   under the ``loop`` operation. The failure MUST be appended to either the
   ``failures`` array or, if the workload executor cannot distinguish between
   errors and failures, the ``errors`` array.

#. Upon receipt of the termination signal, MUST instruct the
   unified test runner to stop looping, as defined in the unified test format.

#. MUST wait for the unified test runner to finish executing.

#. MUST use the unified test runner to retrieve the following
   entities by name from the entity map, if they are set:

   * ``iterations``: The number of iterations that the workload executor
     performed over the looped operations. If set, this value MUST be assigned
     to the workload executor's ``numIterations`` variable. Note that this
     entity may be unset if the workload's ``loop`` operation did not specify
     ``storeIterationsAsEntity``.

   * ``successes``: The number of successful operations that the workload
     executor performed over the looped operations. If set, this value MUST be
     assigned to the workload executor's ``numSuccesses`` variable. Note that
     this entity may be unset if the workload's ``loop`` operation did not
     specify ``storeSuccessesAsEntity``.

   * ``errors``: Array of documents describing the errors that occurred
     while the workload executor was executing the operations. If set, any
     documents in this array MUST be appended to the workload executor's
     ``errors`` array. Note that this entity may be unset if the workload's
     ``loop`` operation did not specify ``storeErrorsAsEntity``.

   * ``failures``: Array of documents describing the failures that occurred
     while the workload executor was executing the operations. If set, any
     documents in this array MUST be appended to the workload executor's
     ``failures`` array. Note that this entity may be unset if the workload's
     ``loop`` operation did not specify ``storeFailuresAsEntity``.

   * ``events``: Array of documents describing the command and CMAP events
     that occurred while the workload executor was executing the operations. If
     set, and documents in this array MUST be appended to the workload
     executor's ``events`` array. Note that this entity may be unset if the
     workload's client entity did not specify ``storeEventsAsEntities``.

#. MUST write the ``events``, ``errors``, and ``failures`` variables to a JSON
   file named ``events.json`` in the current working directory (i.e. directory
   from where the workload executor is being executed). The data written MUST
   be an object with the following fields:

   - ``events``: Array of event objects (e.g. observed command or CMAP events).
     Per the unified test format, each object is expected to have a ``name``
     string field and an ``observedAt`` numeric field, in addition to any other
     fields specific to the event's type.

   - ``errors``: Array of error objects. Per the unified test format, each
     object is expected to have an ``error`` string field and a ``time`` numeric
     field.

   - ``failures``: Array of failure objects. Per the unified test format, each
     object is expected to have an ``error`` string field and a ``time`` numeric
     field.

   Note that is possible for some or all of these arrays to be empty if the
   corresponding data was not reported by the unified test runner and the test
   runner did not propagate an error or failure (which would then be reported by
   the workload executor).

#. MUST write the collected workload statistics into a JSON file named
   ``results.json`` in the current working directory (i.e. the directory
   from where the workload executor is being executed). Workload statistics
   MUST contain the following fields (drivers MAY report additional statistics
   using field names of their choice):

   * ``numErrors``: The number of errors that were encountered during the test.
     This includes errors handled by either the unified test runner or the
     workload executor. The reported value MUST equal the size of the ``errors``
     array reported in ``events.json``.

   * ``numFailures``: The number of failures that were encountered during the
     test. This includes failures handled by either the unified test runner or
     the workload executor. The reported value MUST equal the size of the
     ``failures`` array reported in ``events.json``.

   * ``numSuccesses``: The number of successful operations executed during the
     test. This MAY be -1 if a ``successes`` entity was never reported by the
     unified test runner.

   * ``numIterations``: The number of loop iterations executed during the test.
     This MAY be -1 if an ``iterations`` entity was never reported by the
     unified test runner.

.. note:: The values of ``numErrors`` and ``numFailures`` are used by
   ``astrolabe`` to determine the overall success or failure of a driver
   workload execution. A non-zero value for either of these fields is construed
   as a sign that something went wrong while executing the workload and the test
   is marked as a failure. The workload executor's exit code is **not** used for
   determining success/failure and is ignored.

.. note:: If ``astrolabe`` encounters an error attempting to parse the workload
   statistics written to ``results.json`` (caused, for example, by malformed
   JSON or a nonexistent file), the test will be assumed to have failed.

.. note:: The choice of termination signal used by ``astrolabe`` varies by
   platform. ``SIGINT`` [#f1]_ is used as the termination signal on Linux and
   OSX, while ``CTRL_BREAK_EVENT`` [#f2]_ is used on Windows.

.. note:: On Windows systems, the workload executor is invoked via Cygwin Bash.


Pseudocode Implementation
-------------------------

.. code-block:: javascript

    /* The workloadRunner function accepts a connection string and a stringified
     * JSON blob describing the driver workload. This function will be invoked
     * with arguments parsed from the command-line invocation of the workload
     * executor script. */
    function workloadRunner(connectionString: string, driverWorkload: object): void {

        # Use the driver's unified test runner to run the workload
        const runner = UnifiedTestRunner(connectionString);

        var events = []
        var errors = []
        var failures = []
        var numIterations = -1
        var numSuccesses = -1

        /* The workload executor MUST handle the termination signal gracefully
         * and instruct the unified test runner to stop looping. The termination
         * signal will be used by astrolabe to terminate tests that would
         * otherwise run ad infinitum.
        process.once('SIGINT', function (code) { ... });

        try {
            runner.executeScenario();
        } catch (propagatedError) {
            /* If the test runner propagates an error or failure (e.g. it is not
             * captured by the loop or occurs outside of the loop), it MUST be
             * reported by the workload executor. */
             errors.push({
               error: propagatedError.message,
               time: Date.now() / 1000
             });
        }

        if (runner.entityMap.has('events')) {
            events = events.concat(runner.entityMap.get('events');
        }

        if (runner.entityMap.has('errors')) {
            errors = errors.concat(runner.entityMap.get('errors');
        }

        if (runner.entityMap.has('failures')) {
            failures = failures.concat(runner.entityMap.get('failures');
        }

        if (runner.entityMap.has('iterations')) {
            numIterations = runner.entityMap.get('iterations');
        }

        if (runner.entityMap.has('successes')) {
            numSuccesses = runner.entityMap.get('successes');
        }

        numErrors = errors.length
        numFailures = failures.length

        /* The events.json and results.json files MUST be written to the current
         * working directory from which this script is executed, which is not
         * necessarily the same directory where the script itself resides. */
        fs.writeFile('events.json', JSON.stringify({
            events: events,
            errors: errors,
            failures: failures,
        }));

        fs.writeFile('results.json', JSON.stringify({
            numErrors: numErrors,
            numFailures: numFailures,
            numSuccesses: numSuccesses,
            numIterations: numIterations,
        }));
    }

Reference Implementation
------------------------

`Ruby's workload executor <https://github.com/mongodb-labs/drivers-atlas-testing/blob/master/integrations/ruby/workload-executor>`_
serves as the reference implementation of the script described by this specification.


.. rubric:: Footnotes

.. [#f1] See http://man7.org/linux/man-pages/man7/signal.7.html for details about Linux signals
.. [#f2] See https://docs.microsoft.com/en-us/windows/console/ctrl-c-and-ctrl-break-signals for details about Windows
         console events
