Installing and Running Locally
==============================

.. highlight:: bash

Installing and running ``astrolabe`` is useful when writing integrations for new drivers (see :ref:`integration-guide`)
and when debugging issues uncovered by testing. This document walks through the steps needed to install ``astrolabe``
on your local machine and use it to run Atlas and Kubernetes test scenarios.

Platform Support
----------------

``astrolabe`` runs on Linux, OSX and Windows.

Running ``astrolabe`` requires Python 3.7 or later. To check the version of Python you are running, do::

  $ python --version

Installation
------------

``astrolabe`` can be installed from sources using ``pip``::

  $ python -m pip install git+https://github.com/mongodb-labs/drivers-atlas-testing.git

.. note:: You can use a `virtualenv <https://virtualenv.pypa.io/en/latest/>`_ to isolate your ``astrolabe``
   installation from other Python applications on your system. To do so, run::

     $ python -m virtualenv my_virtualenv && source my_virtualenv/bin/activate

   before running the command to install ``astrolabe``. Note that the ``bin`` directory will be called ``Scripts``
   on Windows systems.

Once installed, check that your installation is working::

  $ astrolabe --version

Exploring the API
-----------------

With the Atlas API credentials now configured, you are ready to use ``astrolabe``. Exploring
``astrolabe``'s capabilities is very easy due to its self-documenting command-line interface. To see a list of
available commands, run::

  $ astrolabe --help

Say, for instance, that you would like to use ``astrolabe`` to create a cluster. Looking at the output of the
``astrolabe --help`` command, you realize that the ``clusters`` command group probably has what you are looking for.
You can explore the usage of this command group by running::

  $ astrolabe clusters --help

Sure enough, the command group has the ``create-dedicated`` command that does what you want to do. Command usage can be
understood by employing a familiar pattern::

  $ astrolabe clusters create-dedicated --help

Debugging
---------

Astrolabe comes with built-in logging functionality that can be customized using the ``--log-level`` option.
Supported logging levels, in decreasing order of verbosity are:

* ``DEBUG``
* ``INFO`` (the default)
* ``WARNING``
* ``ERROR``
* ``CRITICAL``

For example, to use the ``DEBUG`` logging level, do::

  $ astrolabe --log-level DEBUG <command> [COMMAND OPTIONS]

Running Atlas Planned Maintenance Tests
=======================================

Follow these instructions to run an Atlas Planned Maintenance (APM) test.

Configuration
-------------

Before you can start using ``astrolabe`` to run Atlas planned maintenance tests, you must configure it to give it access to the MongoDB Atlas API.

If you haven't done so already, create a
`MongoDB Atlas Organization <https://docs.atlas.mongodb.com/organizations-projects>`_ (this can
only be done via the Atlas UI). Make a note of the name of the Atlas organization.

Depending on the test scenario being executed, you will need either one
or two sets of a `Programmatic API Keys
<https://docs.atlas.mongodb.com/configure-api-access/>`_: a regular
key for Atlas Organization you created with "Organization Owner" permissions,
and potentially a key with Atlas Global Operator permissions (hereafter
referred to as the "admin key"). The admin key generally must be created by
a Cloud team member and would typically be issued for the development environment
of Atlas (`https://cloud-dev.mongodb.com <https://cloud-dev.mongodb.com>`_),
meaning the organization and projects must also be created in the development
environment.

Each API key consists of 2 parts - a public key and a private key.

To configure ``astrolabe`` to use production Atlas and specify only a regular
API key, declare the following variables::

  $ export ATLAS_ORGANIZATION_ID=<Atlas Organization Id>
  $ export ATLAS_API_USERNAME=<API Public Key>
  $ export ATLAS_API_PASSWORD=<API Private Key>

To configure ``astrolabe`` to use development Atlas and specify two sets of
API keys, declare the following variables::

  $ export ATLAS_ORGANIZATION_ID=<Atlas Organization Id>
  $ export ATLAS_API_USERNAME=<API Public Key>
  $ export ATLAS_API_PASSWORD=<API Private Key>
  $ export ATLAS_ADMIN_API_USERNAME=<Admin API Public Key>
  $ export ATLAS_ADMIN_API_PASSWORD=<Admin API Private Key>
  $ export ATLAS_API_BASE_URL=https://cloud-dev.mongodb.com/api/atlas

Finally, use the ``check-connection`` command to confirm that ``astrolabe`` is able to connect to and authenticate
with the Atlas API::

  $ astrolabe check-connection

.. note:: If you encounter an ``AtlasAuthenticationError`` when running ``check-connection``, it means that
   configuration was unsuccessful.

Running Tests
-------------

The ``atlas-tests`` command-group is used for Atlas Planned Maintenance (APM) tests. To run a single APM test, do::

  $ astrolabe atlas-tests run-one <path/to/test-file.yml> -e <path/to/workload-executor> --project-name <atlasProjectName> --cluster-name-salt <randomString>

where:

* ``<path/to/test-file.yml>`` is the absolute or relative path to a test scenario file in the
  :ref:`atlas-test-scenario-format`,
* ``<path/to/workload-executor>`` is the absolute or relative path to the workload executor of the driver to be tested,
* ``<atlasProjectName>`` is the name of the Atlas Project under which the test cluster used for the test will be created,
* ``<randomString>`` is a string that is used as salt while generating the randomized character string that will be
  used as the name of the test cluster.

.. note:: If an Atlas Project of the specified name does not already exist, ``astrolabe`` will create one.

.. note:: Cluster name generation uses the name of the test scenario file along with the value of
   ``--cluster-name-salt`` to generate a randomized character string that is used as the name of the cluster created
   for the purposes of running the test. A deterministic hashing algorithm is employed to generate cluster names so
   using the same ``--cluster-name-salt`` value with a given test file will produce the same cluster name each time.

A common use-case when using ``astrolabe`` is to run a given test several times, in quick succession. This is
necessary during test failure debugging and testing workload executor implementations. By default, ``astrolabe``
automatically deletes a cluster at the end of a test run (this helps keep cloud hosting costs low by minimizing Atlas
cluster uptime). This is quite inconvenient when the test needs to be run multiple times in succession as cluster
creation is very time consuming and can take up to 10 minutes. To ameliorate the situation, the ``run-one`` command
supports a ``--no-delete`` flag that prevents the deletion of the cluster at the end of a test run::

  $ astrolabe atlas-tests run-one ... --no-delete

Using this flag with a given test file and static ``--cluster-name-salt`` value helps significantly reduce waiting
times between successive test runs (you will still need to wait for the cluster to be reconfigured to the initial
configuration).

``astrolabe`` also provides the ``--no-create`` flag which makes it skip
cluster initialization if the cluster already exists. This flag may be used
to further speed up the test runs, but it can only be used for scenarios
where the cluster configuration does not change from the initial one
(otherwise the test would start with the wrong configuration). Using
``--no-delete`` is recommended with ``--no-create``, otherwise each run will
delete the cluster upon completion.

Running Kubernetes Tests
========================

Follow these instructions to run a Kubernetes container scheduling test.

Running Tests
-------------

The ``kubernetes-tests`` command-group is used for Kubernetes tests. To run a single Kubernetes test, do::

  $ astrolabe kubernetes-tests \
      run-one <path/to/test-file.yml> \
      --workload-file <path/to/workload-file.yml>
      --workload-executor <path/to/workload-executor> \
      --connection-string <mongodbConnectionString>

where:

* ``<path/to/test-file.yml>`` is the absolute or relative path to a Kubernetes test scenario file in the
  :ref:`kubernetes-test-scenario-format`,
* ``<path/to/workload-file.yml>`` is the absolute or relative path to a workload file in the
  :ref:`kubernetes-test-scenario-format`,
* ``<path/to/workload-executor>`` is the absolute or relative path to the workload executor of the driver to be tested,
* ``<mongodbConnectionString>`` is the connection string

For example::

  $ DRIVER_DIRNAME=go \
      astrolabe kubernetes-tests \
      run-one tests/kubernetes/kind/deletePod.yml \
      --workload-file workloads/reads.yml \
      --workload-executor integrations/$DRIVER_DIRNAME/workload-executor \
      --connection-string "mongodb://user:12345@localhost:31181,localhost:31182,localhost:31183/admin?ssl=true&tlsCertificateKeyFile=$(pwd)/mongodb_tls_cert.pem&tlsCAFile=$(pwd)/kubernetes/kind/rootCA.pem"
