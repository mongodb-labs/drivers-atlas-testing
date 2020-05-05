Frequently Asked Questions
==========================

.. contents::

Why do I keep seeing ``atlasclient.exceptions.AtlasAuthenticationError: 401: Unauthorized.`` errors?
----------------------------------------------------------------------------------------------------

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

