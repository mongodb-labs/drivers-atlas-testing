Drivers Atlas Testing
=====================

The Drivers Atlas Testing project validates the behavior of drivers against
Atlas clusters. For example, a test could be to perform queries or writes
in a loop while Atlas performs a maintenance operation, and assert that all
queries and writes complete successfully.

The project consists of the following principal components:

- Astrolabe - the orchestration utility.
- :doc:`Workload executors <spec-workload-executor>` - wrappers providing
  a common interface to each driver's unified test runner.
- Each driver's unified test runner.
- :doc:`The test scenario specification <spec-test-format>`.

Drivers Atlas Testing' architecture is described in more detail in the
:doc:`architecture` page.

Documentation Overview
----------------------

:doc:`installing-running-locally`
  Instructions for installing ``astrolabe`` and running Atlas Planned Maintenance Tests from your local machine.

:doc:`integration-guide`
  Instructions on how to use ``astrolabe`` to test your driver against MongoDB Atlas clusters in Evergreen.

:doc:`spec-workload-executor`
  Information about the workload executor script that drivers must implement in order to use ``astrolabe``.

:doc:`spec-test-format`
  Information about the file format used to define Atlas Planned Maintenance Tests.

:doc:`technical-design`
  Background reading about this testing framework's architecture and design methodology.

:doc:`faq`
  Answers to questions and issues that come up often.

Table of Contents
-----------------

.. toctree::
   :maxdepth: 2

   architecture
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
