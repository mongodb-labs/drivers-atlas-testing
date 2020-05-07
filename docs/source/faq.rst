Frequently Asked Questions
==========================

Why do I keep seeing ``AtlasAuthenticationError: 401: Unauthorized.`` errors while trying to use ``astrolabe``?
---------------------------------------------------------------------------------------------------------------

Applications can only be granted programmatic access to MongoDB Atlas using an
`API key <https://docs.atlas.mongodb.com/configure-api-access/#programmatic-api-keys>`_. If you are
seeing ``401: Unauthorized`` error codes from MongoDB Atlas, it means that you have either
not provided an API key, or that the API key that you have provided is has expired. Please
see the `MongoDB Atlas API <https://docs.atlas.mongodb.com/>`_ documentation for instructions on
how to create programmatic API keys.

``astrolabe`` can be configured to use API keys in one of 2 ways:

* Using the `-u/--username` and `-p/--password` command options::

    $ astrolabe -u <publicKey> -p <privateKey> check-connection

* Using the ``ATLAS_API_USERNAME`` and ``ATLAS_API_PASSWORD`` environment variables::

    $ ATLAS_API_USERNAME=<publicKey> ATLAS_API_PASSWORD=<privateKey> astrolabe check-connection

.. _faq-why-custom-distro:

Why should we use the custom ``ubuntu1804-drivers-atlas-testing`` distro?
-------------------------------------------------------------------------

MongoDB Atlas restricts the number of clusters in an Atlas Project to 25. Since
`this project <https://github.com/mongodb-labs/drivers-atlas-testing>`_ runs the entire
build matrix in its in
`evergreen configuration <https://github.com/mongodb-labs/drivers-atlas-testing/blob/master/.evergreen/config.yml>`_
under a single Atlas project, it often ends up running into this limitation which causes
hard-to-diagnose test failures (see `#45 <https://github.com/mongodb-labs/drivers-atlas-testing/issues/45>`_,
`#46 <https://github.com/mongodb-labs/drivers-atlas-testing/issues/46>`_, and
`#48 <https://github.com/mongodb-labs/drivers-atlas-testing/issues/45>`_). To mitigate this issue,
we need to limit the number of concurrent builds in the
`drivers-atlas-testing <https://evergreen.mongodb.com/waterfall/drivers-atlas-testing>`_ Evergreen project to less
than 25. Evergreen does not currently have a way to enforce such a limit, so instead we have created this
custom distro which is limited to 25 hosts. While not foolproof, this workaround helps avoid the aforementioned
failures in most usage scenarios.

.. _faq-why-startup-time:

What is the purpose of the ``ASTROLABE_EXECUTOR_STARTUP_TIME`` environment variable?
------------------------------------------------------------------------------------

This test framework's architecture (see :ref:`astrolabe-architecture`) delegates the responsibilities of
invoking the workload executor as well as starting the Atlas planned maintenance to ``astrolabe``. Since
the workload executor is run in a subprocess, there is no straightforward way for ``astrolabe`` to ascertain
whether a workload executor is in the process of initialization or if it is, in fact, already running operations
against the test cluster. This limitation, when combined with a workload executor that runs particularly slowly
can result in failures, e.g.:

* The maintenance completes and ``astrolabe`` terminates the workload executor before it can run any operations.
* The workload executor only starts running operations when cluster maintenance is already underway.

To avoid this situation, users can set the ``ASTROLABE_EXECUTOR_STARTUP_TIME`` environment variable to a value
greater than the number of seconds it takes their workload executor to start. When this value is set, ``astrolabe``
will wait for ``ASTROLABE_EXECUTOR_STARTUP_TIME`` seconds before implementing the maintenance plan thereby avoiding
the aforementioned issues.
