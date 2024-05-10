# astrolabe

[![Documentation Status](https://readthedocs.org/projects/drivers-atlas-testing/badge/?version=latest)](http://drivers-atlas-testing.readthedocs.io/en/latest/?badge=latest)

Developer tools for testing
[Drivers](https://docs.mongodb.com/ecosystem/drivers/) against [MongoDB
Atlas](https://www.mongodb.com/cloud/atlas). See
[GitHub](https://github.com/mongodb-labs/drivers-atlas-testing) for the
latest source.

## About

The Astrolabe distribution contains tools for automating Atlas
operations and running Atlas Planned Maintenance tests. The
`atlasclient` package provides programmatic access to the [MongoDB Atlas
API](https://docs.atlas.mongodb.com/api/) via a fluent interface. The
`astrolabe` package provides a convenient, command-line interface to the
`atlasclient` and also contains the test harnesses necessary to run
Atlas Planned Maintenance specification tests.

Astrolabe supports Python 3.8+.

## Installation

Astrolabe can be installed with [pip](http://pypi.python.org/pypi/pip):

```bash
python -m pip install astrolabe
```

You can also download the project source and do:

```bash
python -m pip install .
```

## Dependencies

Astrolabe supports CPython 3.8+.

Astrolabe requires [Click](https://pypi.org/project/click/),
[requests](https://pypi.org/project/requests/),
[PyMongo](https://pypi.org/project/pymongo/),
[dnspython](https://pypi.org/project/pymongo/),
[PyYAML](https://pypi.org/project/PyYAML/), and
[junitparser](https://pypi.org/project/junitparser/).

## Documentation

Documentation is available on [ReadtheDocs](http://drivers-atlas-testing.readthedocs.io/en/latest/).

To build the documentation, you will need to install
[mkdocs](https://www.mkdocs.org/getting-started/). 

Run `mkdocs serve` to see a live view of the docs.

## Linting and Formatting

This repo uses [pre-commit](https://pypi.org/project/pre-commit/) for
managing linting. `pre-commit` performs various checks on the files and
uses tools that help follow a consistent style within the repo.

To set up `pre-commit` locally, run:

``` bash
brew install pre-commit
pre-commit install
```

To run `pre-commit` manually, run `pre-commit run --all-files`.

To run a manual hook like `shellcheck` manually, run:

``` bash
pre-commit run --all-files --hook-stage manual shellcheck
```
