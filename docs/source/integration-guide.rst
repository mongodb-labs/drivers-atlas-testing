Integration Guide
=================

This guide explains how to use ``astrolabe`` to add Atlas Planned Maintenance testing to your driver.


--------
Overview
--------

Driver projects looking to integrate this framework into their project codebase should follow the following steps:

#. :ref:`integration-step-workload-executor` for their driver project.
#. :ref:`integration-step-driver-installer` for their driver project.
#. :ref:`integration-step-evergreen-configuration` of the ``drivers-atlas-testing`` project.


We will walk through each of these steps in detail in the following sections.

Setting up
----------

#. Start by forking the `drivers-atlas-testing <https://github.com/mongodb-labs/drivers-atlas-testing>`_
   repository and creating a new branch on your fork::

     $ git clone git@github.com:<your-github-username>/drivers-atlas-testing.git
     $ cd drivers-atlas-testing && git checkout -b add-driver-integration

#. Create a new directory for your driver under the ``drivers-atlas-testing/.evergreen`` directory.
   It is recommended that drivers use the name of their language to name their folder.
   Languages that have multiple drivers should use subdirectories named after the driver (e.g. for Python,
   we should create ``.evergreen/python/pymongo`` and ``.evergreen/python/motor``)::

   $ mkdir -p .evergreen/driver-language/project-name

.. note::

   The path to the newly created folder(s) will henceforth be referred to in this guide as ``DRIVER_DIRNAME``.


.. _integration-step-workload-executor:

---------------------------------------
Implementing a Workload Executor Script
---------------------------------------

Drivers must implement this script in accordance with the specification, see
:ref:`workload-executor-specification`. In addition to exposing the user-facing API described in the specification,
the workload executor script:

* MUST set a non-zero exit-code if it terminates unexpectedly or in the event that the driver workload being executed
  fails.
* MUST set a zero exit-code if the workload executes successfully and there are no failures.
* MUST log workload statistics as a JSON object dumped to STDERR at the end of the run. Workload statistics consist of
  the following keys:

  * numErrors: the number of operation errors that were encountered during the test.
  * numFailures: the number of operation failures that were encountered during the test.

* MUST log all output from the driver during the test run, including any tracebacks, and informational messages to
  STDOUT.
* MUST NOT override any of the URI options specified in the incoming connectionString.
* MUST NOT augment the incoming connectionString with any additional URI options.

Finally, drivers SHOULD save their workload executor scripts in the ``DRIVER_DIRNAME`` directory.

.. note::

   All `Evergreen expansions <https://github.com/evergreen-ci/evergreen/wiki/Project-Files#expansions>`_
   for a given build variant are available to the workload executor script at runtime as environment variables.
   The script can make use of any of these environment variables but must ensure that they are written in a way that
   prevents accidentally leaking Atlas API credentials and MongoDB user credentials. See
   :ref:`evg-defining-environment-variables` for details.

.. note::

   Users MUST ensure that the ``WORKLOAD_EXECUTOR`` evergreen expansion is set in all buildvariants. ``astrolabe``
   uses the value of this expansion to invoke the workload executor.
   See :ref:`integration-note-workload-executor-invocation` for details.

.. note::

   The workload executor be invoked with the working directory set to the ``astrolabe`` project root.


.. _integration-note-workload-executor-invocation:

Specifying the Workload Executor Invocation
-------------------------------------------

Different languages will have different kinds of workload executors. Compiled languages, for example, might have
as their workload executor a standalone binary whereas interpreted languages would likely use a script that
would need to be executed using the appropriate interpreter. Furthermore, drivers may need to employ different
workload executor scripts on different platforms. To support these various usage scenarios, users can
specify the full command string needed to execute the workload executor. This is done by setting the
``WORKLOAD_EXECUTOR`` evergreen expansion to the appropriate value.

For example, in the case of PyMongo on *nix systems we set::

  WORKLOAD_EXECUTOR: "/opt/python/3.7/bin/python3 .evergreen/python/pymongo/workload-executor.py"

Whereas on Windows systems, the same definition would look something like this::

  WORKLOAD_EXECUTOR: "C:/python/Python37/python.exe .evergreen/python/pymongo/workload-executor.py"

.. note::

   Paths appearing in the ``WORKLOAD_EXECUTOR`` definition must either be absolute OR be relative to the
   ``astrolabe`` project root directory.

.. note::

   Drivers MUST ensure that the ``WORKLOAD_EXECUTOR`` variable is defined for each buildvariant. Failure to define
   this variable will result in system failures on Evergreen. See :ref:`evg-defining-environment-variables`
   for details.


.. _integration-step-driver-installer:

--------------------------------------
Implementing a Driver Installer Script
--------------------------------------

Drivers must implement this standalone script to perform all setup/installation-related tasks for their driver.
The installer script MUST be saved in the ``DRIVER_DIRNAME`` directory under the name ``install-driver.sh``.
The executable permission bit MUST be set for the install script file before it is committed to git.

This script can be used to perform any number of arbitrary tasks related to setting up the environment for
the workload executor to be executed within. It MUST NOT however, clone the driver source repository as this
is done by one of the shared Evergreen tasks.

.. note::

   All `Evergreen expansions <https://github.com/evergreen-ci/evergreen/wiki/Project-Files#expansions>`_
   for a given build variant are available to the driver installer script at runtime as environment variables.
   The script can make use of any of these environment variables but must ensure that they are written in a way that
   prevents accidentally leaking Atlas API credentials and MongoDB user credentials. See
   :ref:`evg-defining-environment-variables` for details.

.. note::

   The driver installer script will be executed with the working directory set to the ``astrolabe`` project root.

.. note::

   Driver source code which downloaded by the shared Evergreen configuration will reside in a folder matching
   the driver source repository name (e.g. ``mongo-java-driver`` for Java) within the ``astrolabe`` project root.


.. _integration-step-evergreen-configuration:

------------------------------------
Updating the Evergreen Configuration
------------------------------------

Finally, to add your driver to the Evergreen test matrix, you will need to update the Evergreen configuration file
at ``.evergreen/config.yml``. First, you must ensure that axis entries for your desired ``platform`` and ``runtime``
are in place.

.. _evg-adding-a-platform:

Adding a Platform
-----------------

The Atlas Planned Maintenance tests can be run on all platforms which have a Python 3.5+ binary installed.
Each entry to the ``platform`` axis has the following fields:

* ``id`` (required): unique identifier for this ``platform`` axis entry.
* ``display_name`` (optional): plaintext name for this platform that will be used to display test runs.
* ``run_on`` (required): evergreen distro name for this platform
* ``variables.PYTHON3_BINARY`` (required): path to the Python 3.5+ binary on the distro. This is used to run
  ``astrolabe``.
* ``variables.PYTHON_BIN_DIR`` (required): name of directory in which Python install executables. This is always
  ``bin`` on \*nix systems and ``Scripts`` on Windows.

Here is an example of a ``platform`` axis entry for the ``Ubuntu-16.04`` platform::

  - id: platform
    display_name: OS
    values:
      - id: ubuntu-16.04
        display_name: "Ubuntu 16.04"
        run_on: ubuntu1604-test
        variables:
          PYTHON3_BINARY: "/opt/python/3.7/bin/python3"
          PYTHON_BIN_DIR: "bin"

.. note::

  To encourage re-use of ``platform`` entries across driver projects, it is recommended that no driver-specific
  expansions be added to the ``variables`` section of the platform definition.

.. _evg-adding-a-runtime:

Adding a Runtime
----------------

The ``runtime`` axis is an optional way for drivers to differentiate test runs on a common platform.
For interpreted languages, for example, the ``runtime`` axis can be used to run tests with different interpreter
versions (see the Python driver's integration for an example). For compiled languages, the ``runtime`` axis may be
used to test with different compiler versions. Here is an example of a ``runtime`` axis entry that defines the
``PYTHON_BINARY`` variable which is used by the Python driver's scripts to determine which version of the Python
runtime to use for running the tests, and also defines the ``WORKLOAD_EXECUTOR`` variable which is used by
``astrolabe`` to determine how to invoke PyMongo's workload executor script::

  - id: runtime
    display_name: runtime
    values:
      - id: python27
        display_name: CPython-2.7
        variables:
          PYTHON_BINARY: "/opt/python/2.7/bin/python"
          WORKLOAD_EXECUTOR: "${PYMONGO_VIRTUALENV_NAME}/${PYTHON_BIN_DIR}/python.exe .evergreen/${DRIVER_DIRNAME}/workload-executor.py"

Runtime entries are not expected to be shared across driver projects so drivers are encourage to add their own,
new entries rather than augmenting existing entries used by other drivers.

.. note::

   Use of the ``runtime`` axis is optional. You may simply omit this axis from your driver's buildvariant
   definitions should you not require it.

.. _evg-adding-a-driver:

Adding a Driver
---------------

Once the platform and runtime are in place, you can add entries to the ``driver`` axis for your driver.
The number of entries you will need to add for your driver will depend upon how many versions of your driver
you intend to test. Each entry has the following fields:

* ``id`` (required): unique identifier for this ``driver`` axis entry.
* ``display_name`` (optional): plaintext name for this driver version that will be used to display test runs.
* ``variables.DRIVER_DIRNAME`` (required): path, relative to the ``astrolable/.evergreen`` directory where the
  driver-specific scripts live.
* ``variables.DRIVER_REPOSITORY`` (required): HTTPS URL that can be used to clone the source repository of the
  driver to be tested.
* ``variables.DRIVER_REVISION`` (required): git revision-id corresponding to the driver version that is to be tested.
  This can be a branch name (e.g. ``"master"``) or a tag (e.g. ``"1.0.0"``).
* ``variables.WORKLOAD_EXECUTOR`` (conditional): full command string to be used for invoking
  the driver's workload executor. See :ref:`integration-note-workload-executor-invocation` for details on how to
  specify this value. Users may omit this variable if it is defined under a different axis of the build matrix.

All additional expansions that are relied upon by the driver's install and/or workload executor scripts
should also be declared in the ``variables`` section of the driver definition. Finally, an entry can be added to
the ``buildvariants`` to run the tests on the desired ``driver``, ``platform``, and ``runtime`` combinations.
It is recommended that drivers use the ``all`` task tag to to enable all tests on their driver.

Here is an example of the ``driver``-axis entry for the Python driver (note that in this particular example, the
required variable ``WORKLOAD_EXECUTOR`` is defined under the ``runtime`` axis and therefore omitted from the
``driver`` axis definition::

  - id: driver
    display_name: driver
    values:
      - id: pymongo-master
        display_name: "PyMongo (master)"
        variables:
          DRIVER_DIRNAME: "python/pymongo"
          DRIVER_REPOSITORY: "https://github.com/mongodb/mongo-python-driver"
          DRIVER_REVISION: "master"
          PYMONGO_VIRTUALENV_NAME: "pymongotestvenv"

And the corresponding buildvariant definition::

  buildvariants:
  - matrix_name: "tests-python"
    matrix_spec:
      driver: ["pymongo-master"]
      platform: ["ubuntu-16.04"]
      runtime: ["python27"]
    display_name: "${driver} ${platform} ${runtime}"
    tasks:
      - ".all"

.. _evg-defining-environment-variables:

------------------------------
Defining Environment Variables
------------------------------

There are 2 places where you can define the variables needed by your driver's integration scripts
in the Evergreen configuration file:

* The ``driver``-axis: ``key: value`` pairs added to the ``variables`` field of an entry in this axis
  will be available to the driver installer and workload executor scripts as environment variables at runtime.
  This is the ideal place to define variables that are common across all buildvariants of a particular driver.
  See :ref:`evg-adding-a-driver` for details.
* The ``runtime``-axis: ``key-value`` pairs added to the ``variables`` field on an entry in this axis
  will be available to the driver installer and workload executor scripts as environment variables at runtime, provided
  the buildvariant uses the ``runtime`` axis (use of this axis is optional). This is the ideal place to define
  variables that vary across buildvariants for a particular driver. See :ref:`evg-adding-a-runtime` for details.

.. note::

  The ``WORKLOAD_EXECUTOR`` variable is **required** by ``astrolabe``. It is upto the implementer to decide whether
  to specify it under the ``driver``-axis entry or the ``runtime``-axis entries.

.. note::

  To encourage re-use of ``platform`` entries across driver projects, it is recommended that no driver-specific
  expansions be added to the ``variables`` section of the platform definition.

.. note::

  Users are asked to be extra cautious while dealing with environment variables that contain sensitive secrets.
  Using these variables in a script that sets ``-xtrace`` can, for instance, result in leaking these secrets
  into Evergreen's log output.
