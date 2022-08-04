Welcome to astrolabe's documentation!
=====================================

**astrolabe** is a toolkit for testing MongoDB driver behavior during common MongoDB cluster
reconfiguration operations. It currently supports testing MongoDB drivers during Atlas Planned
Maintenance events and Kubernetes container scheduling events.

Documentation Overview
----------------------

:doc:`installing-running-locally`
  Instructions for installing ``astrolabe`` and running tests from your local machine.

:doc:`integration-guide`
  Instructions on how to use ``astrolabe`` to test your driver against MongoDB Atlas clusters in Evergreen.

:doc:`spec-workload-executor`
  Information about the workload executor script that drivers must implement in order to use ``astrolabe``.

:doc:`spec-test-format`
  Information about the file format used to define Atlas Planned Maintenance and Kubernetes tests.

:doc:`technical-design`
  Background reading about this testing framework's architecture and design methodology.

:doc:`faq`
  Answers to questions and issues that come up often.

Table of Contents
-----------------

.. toctree::
   :maxdepth: 2

   installing-running-locally
   integration-guide
   spec-workload-executor
   spec-test-format
   technical-design
   faq

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
