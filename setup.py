import io
import os

from setuptools import setup


# Single source the version.
version_file = os.path.realpath(os.path.join(
    os.path.dirname(__file__), 'astrolabe', 'version.py'))
version = {}
with io.open(version_file, 'rt', encoding='utf-8') as fp:
    exec(fp.read(), version)


# Dynamically generate long-description.
readme_file = os.path.realpath('README.rst')
if os.path.exists(readme_file) and os.path.isfile(readme_file):
    with io.open('README.rst', 'rt', encoding='utf-8') as fp:
        readme_content = f.read()
else:
    readme_content = ''


setup(
    name='astrolabe',
    version=version['__version__'],
    description=("Command-line utility for testing Drivers against MongoDB "
                 "Atlas <https://www.mongodb.com/cloud/atlas>"),
    long_description=readme_content,
    author="MongoDB, Inc.",
    author_email="mongodb-user@googlegroups.com",
    maintainer="Prashant Mital",
    maintainer_email="prashant.mital@mongodb.com",
    url="https://github.com/mongodb-labs/drivers-atlas-testing",
    keywords=["mongodb", "mongodbatlas", "atlas", "mongo"],
    license="Apache License, Version 2.0",
    python_requires=">=3.5",
    packages=["atlasclient", "astrolabe"],
    install_requires=[
        'click>=7,<8',
        'requests>=2,<3',
        'pymongo>=3.10,<4',
        'dnspython>=1.16,<2',
        'pyyaml>=5,<6',
        'junitparser>=1,<2'],
    entry_points={
        'console_scripts': ['astrolabe=astrolabe.cli:cli']},
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Software Development :: Testing"])
