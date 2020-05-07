.. _integration-guide:

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

#. Create a new directory for your driver under the ``drivers-atlas-testing/integrations`` directory.
   It is recommended that drivers use the name of their language to name their folder.
   Languages that have multiple drivers should use subdirectories named after the driver (e.g. for Python,
   we could create ``integrations/python/pymongo`` and ``integrations/python/motor``)::

   $ mkdir -p integrations/<driver-language>/<project-name>

.. note:: The path to the newly created folder(s) will henceforth be referred to in this guide as ``DRIVER_DIRNAME``.


.. _integration-step-workload-executor:

---------------------------------------
Implementing a Workload Executor Script
---------------------------------------

Drivers must implement this script in accordance with the specification - see :ref:`workload-executor-specification`.
The workload executor MUST be saved in the ``DRIVER_DIRNAME`` directory under the name ``workload-executor``.
The executable permission bit MUST be set for the workload executor file *before* it is committed to git.

.. note:: All `Evergreen expansions <https://github.com/evergreen-ci/evergreen/wiki/Project-Files#expansions>`_
   for a given build variant are available to the workload executor script at runtime as environment variables.
   The script can make use of any of these environment variables but should ensure that it does not accidentally
   leak the Atlas API credentials and MongoDB user credentials. See :ref:`evg-defining-environment-variables` for
   details.

.. note:: The workload executor be invoked with the working directory set to the ``astrolabe`` project root.

.. _wrapping-workload-executor-shell-script:

Wrapping native workload executors with a shell script
------------------------------------------------------

Different languages will have different kinds of workload executors. Compiled languages, for example, might have
as their workload executor a standalone binary whereas interpreted languages would likely use a script that
needs to be invoked using an interpreter. Furthermore, drivers may need to employ different
workload executor scripts on different platforms. To support these various usage scenarios, users can
wrap the actual call to a natively implemented workload executor in a shell script such that exposes the
API desired by the :ref:`workload-executor-specification` specification.

.. note:: For example, PyMongo's ``astrolabe`` integration uses this pattern to implement its
   `workload executor <https://github.com/mongodb-labs/drivers-atlas-testing/blob/master/integrations/python/pymongo/workload-executor>`_.

Testing/validating a workload executor script
---------------------------------------------

Workload executor scripts are cumbersome to test due to the amount of setup required before they can be
invoked. In order to test a workload executor, at a minimum, you need:

* an ``astrolabe`` installation,
* an installation of the driver whose workload executor is to be tested,
* a connection string to the MongoDB instance against which the workload executor will run operations, and
* a test YAML file containing a driver workload that can be used to run the test.

While you can always run a patch build with the workload executor (having first updated the evergreen configuration
as outlined in :ref:`integration-step-evergreen-configuration` of course), your builds will take a while
to complete (provisioning Atlas clusters takes time) resulting in a large wait before you can check whether
the workload executor behaved as expected.

To streamline the process of testing your workload executor implementation, the ``drivers-atlas-testing`` Evergreen
project offers a special task called ``validate-workload-executor``. This task spins up a MongoDB cluster on the
Evergreen test instance and runs a series of checks against the workload executor that has been provided. It may
be used during the implementation of workload executors as a convenient way to test script functionality.

.. note:: The ``validate-workload-executor`` task only appears on patch builds.

.. note:: If your workload executor takes a while to start, validation may fail due to ``astrolabe`` terminating
   the workload executor before any driver operations have been run (see :ref:`faq-why-startup-time` for details).
   You can workaround this issue by declaring the ``ASTROLABE_EXECUTOR_STARTUP_TIME`` environment variable (see
   :ref:`evg-adding-a-driver`).

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

.. note:: All `Evergreen expansions <https://github.com/evergreen-ci/evergreen/wiki/Project-Files#expansions>`_
   for a given build variant are available to the driver installer script at runtime as environment variables.
   The script can make use of any of these environment variables but must ensure that they are written in a way that
   prevents accidentally leaking Atlas API credentials and MongoDB user credentials. See
   :ref:`evg-defining-environment-variables` for details.

.. note:: The driver installer script will be executed with the working directory set to the ``astrolabe`` project root.

.. note:: Driver source code which downloaded by the shared Evergreen configuration will reside in a folder matching
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

.. attention:: Drivers wanting to run the Atlas Planned Maintenance test-suite on Linux systems
   are **strongly advised** to use the custom
   `ubuntu1804-drivers-atlas-testing <https://evergreen.mongodb.com/distros#%23ubuntu1804-drivers-atlas-testing>`_
   distro for running their tests. See :ref:`faq-why-custom-distro` for details.

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

.. note:: To encourage re-use of ``platform`` entries across driver projects, it is recommended that no
   driver-specific expansions be added to the ``variables`` section of the platform definition.

.. _evg-adding-a-runtime:

Adding a Runtime
----------------

The ``runtime`` axis is an optional way for drivers to differentiate test runs on a common platform.
For interpreted languages, for example, the ``runtime`` axis can be used to run tests with different interpreter
versions (see the Python driver's integration for an example). For compiled languages, the ``runtime`` axis may be
used to test with different compiler versions. Here is an example of a ``runtime`` axis entry that defines the
``PYTHON_BINARY`` variable which is used by the Python driver's scripts to determine which version of the Python
runtime to use for running the tests::

  - id: runtime
    display_name: runtime
    values:
      - id: python27
        display_name: CPython-2.7
        variables:
          PYTHON_BINARY: "/opt/python/2.7/bin/python"

Runtime entries are not expected to be shared across driver projects so drivers are encourage to add their own,
new entries rather than augmenting existing entries used by other drivers.

.. note:: Use of the ``runtime`` axis is optional. You may simply omit this axis from your driver's buildvariant
   definitions should you not require it.

.. _evg-adding-a-driver:

Adding a Driver
---------------

Once the platform and runtime are in place, you can add entries to the ``driver`` axis for your driver.
The number of entries you will need to add for your driver will depend upon how many versions of your driver
you intend to test. Each entry has the following fields:

* ``id`` (required): unique identifier for this ``driver`` axis entry.
* ``display_name`` (optional): plaintext name for this driver version that will be used to display test runs.
* ``variables.DRIVER_DIRNAME`` (required): path, relative to the ``astrolable/integrations`` directory where the
  driver-specific scripts live.
* ``variables.DRIVER_REPOSITORY`` (required): HTTPS URL that can be used to clone the source repository of the
  driver to be tested.
* ``variables.DRIVER_REVISION`` (required): git revision-id corresponding to the driver version that is to be tested.
  This can be a branch name (e.g. ``"master"``) or a tag (e.g. ``"1.0.0"``).
* ``variables.ASTROLABE_EXECUTOR_STARTUP_TIME`` (optional): the amount of time ``astrolabe`` should wait after
  invoking the workload executor, but before applying the maintenance plan. It is recommended that this value be
  explicitly set by all drivers whose workload executor implementations take >1 second to start. Failing to do so
  can result in hard-to-debug failures. See :ref:`faq-why-startup-time` for details.

All additional expansions that are relied upon by the driver's install and/or workload executor scripts
should also be declared in the ``variables`` section of the driver definition. Finally, an entry can be added to
the ``buildvariants`` to run the tests on the desired ``driver``, ``platform``, and ``runtime`` combinations.
It is recommended that drivers use the ``all`` task tag to to enable all tests on their driver.

Here is an example of the ``driver``-axis entry for the Python driver::

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

.. note:: To encourage re-use of ``platform`` entries across driver projects, it is recommended that no
   driver-specific expansions be added to the ``variables`` section of the platform definition.

.. note:: Users are asked to be extra cautious while dealing with environment variables that contain sensitive secrets.
   Using these variables in a script that sets ``-xtrace`` can, for instance, result in leaking these secrets
   into Evergreen's log output.
