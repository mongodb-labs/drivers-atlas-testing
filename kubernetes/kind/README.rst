====
Run a MongoDB Replicaset Using Kind
====

The scripts and configurations in this directory create a 3-node MongoDB replicaset in a local Kind cluster with authentication and TLS enabled. `Kind <https://kind.sigs.k8s.io/>`_ is a tool for running a local Kubernetes cluster in a Docker container.

Prerequisites
-------------

1. `Install Docker <https://docs.docker.com/engine/install/>`_.

  *IMPORTANT:* If you're using Docker on macOS or Windows, you need to increase the maximum memory usage by . See the `Settings for Docker Desktop <https://kind.sigs.k8s.io/docs/user/quick-start/#settings-for-docker-desktop>`_ section of the Kind setup for instructions.

2. Install the `kind <https://kind.sigs.k8s.io/docs/user/quick-start/#installation>`_, `helm <https://helm.sh/docs/intro/install/>`_, `kubectl <https://kubernetes.io/docs/tasks/tools/#kubectl>`_, `cmctl <https://cert-manager.io/docs/usage/cmctl/#installation>`_, and `jq <https://stedolan.github.io/jq/download/>`_ command line tools in the system ``PATH``.

Usage
-----

**Create a Cluster**

To create a cluster, make sure Docker is running, then run the create Bash script::

  $ create.sh

The create script will create a Kind cluster and start a 3-node MongoDB replicaset listening on ``localhost`` ports 31181-31183 with user:password ``user:12345``. It writes the TLS certificate to ``mongodb_tls_cert.pem`` in the current directory.

**Connect to a Cluster**

To connect to the MongoDB replicaset with ``mongosh``, run the following command::

  $ mongosh \                                     
    "mongodb://user:12345@localhost:31181,localhost:31182,localhost:31183/admin?ssl=true" \
    --tls \
    --tlsCAFile ./kubernetes/kind/rootCA.pem \
    --tlsCertificateKeyFile ./mongodb_tls_cert.pem

**Delete a Cluster**

To delete the MongoDB replicaset and Kind cluster, run the delete Bash script::

  $ delete.sh
