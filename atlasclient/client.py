import requests

from atlasclient.configuration import get_client_configuration
from atlasclient.exceptions import (
    AtlasAuthenticationError, AtlasClientError, AtlasApiError,
    AtlasRateLimitError)
from atlasclient.utils import enable_http_logging, JSONObject


_EMPTY_PATH_ERR_MSG_TEMPLATE = ('Calling {} on an empty API path is not '
                                'supported.')


class _ApiComponent:
    """Private class for dynamically constructing resource paths."""
    def __init__(self, client, path=None):
        self._client = client
        self._path = path

    def __repr__(self):
        return '<ApiComponent: %s>' % self._path

    def __getitem__(self, path):
        if self._path is not None:
            path = '%s/%s' % (self._path, path)
        return _ApiComponent(self._client, path)

    def __getattr__(self, path):
        return self[path]

    def get(self, **params):
        if self._path is None:
            raise TypeError(_EMPTY_PATH_ERR_MSG_TEMPLATE.format('get()'))
        return self._client.request('GET', self._path, **params)

    def patch(self, **params):
        if self._path is None:
            raise TypeError(_EMPTY_PATH_ERR_MSG_TEMPLATE.format('patch()'))
        return self._client.request('PATCH', self._path, **params)

    def post(self, **params):
        if self._path is None:
            raise TypeError(_EMPTY_PATH_ERR_MSG_TEMPLATE.format('post()'))
        return self._client.request('POST', self._path, **params)

    def delete(self, **params):
        if self._path is None:
            raise TypeError(_EMPTY_PATH_ERR_MSG_TEMPLATE.format('delete()'))
        return self._client.request('DELETE', self._path, **params)

    def get_path(self):
        return self._path


class _ApiResponse:
    """Private wrapper class for processing HTTP responses."""
    def __init__(self, response, request_method, json_data):
        self.resource_url = response.url
        self.headers = response.headers
        self.request_method = request_method
        self.data = json_data

    def __repr__(self):
        return '<{}: {} {}>'.format(self.__class__.__name__,
                                     self.request_method, self.resource_url)


class AtlasClient:
    """An easy-to-use MongoDB Atlas API client for Python. """
    def __init__(self, config):
        """
        Client for the `MongoDB Atlas API
        <https://docs.atlas.mongodb.com/api/>`_.

        The client exposes a fluent interface to the Atlas API. To get started,
        users must first use the Atlas Web UI to `Configure API Access
        <https://docs.atlas.mongodb.com/configure-api-access/>`_. A client can
        then be instantiated using the public and private API keys::

            client = AtlasClient.from_configuration_options(
                username=public_key, password=private_key)

        Use the :meth:`~atlasclient.client.AtlasClient.root` method to check
        that the credentials are valid::

            print(client.root.get().data)

        GET example - Get One Cluster
        (GET /groups/{GROUP-ID}/clusters/{CLUSTER-NAME})

            cluster_details = client.groups['5e3b3687f2a30b7ec2d220ab'].clusters['cluster1'].get()

        POST example - Create a Project
        (POST /groups)

            project = client.groups.post(
                name='new_project', orgId='5afdee7f96e8212ab7171c61')

        PATCH example - Disable server-side Javascript
        (PATCH /groups/{GROUP-ID}/clusters/{CLUSTER-NAME}/processArgs)

            new_process_args = client.groups['5e3b3687f2a30b7ec2d220ab'].clusters['cluster1'].processArgs.patch(
                javascriptEnabled=False)

        DELETE example - Delete a Cluster
        (DELETE /groups/{GROUP-ID}/clusters/{CLUSTER-NAME})

            client.groups['5e3b3687f2a30b7ec2d220ab'].clusters['cluster1'].delete()


        .. note:: all HTTP methods (get, post, patch, delete) have support
          user-specified JSON input via the ``json`` keyword argument.

        :Parameters:
          - `config` (instance of
            :class:`~atlasclient.configuration.ClientConfiguration`):
            configuration of the client to be created.
        """
        self.config = config
        if config.verbose:
            enable_http_logging(config.verbose)

    @classmethod
    def from_configuration_options(cls, *, username, password,
                                   base_url=None, api_version=None,
                                   timeout=None, verbose=None):
        """
        Constructor for creating an AtlasClient object directly from
        configuration option values.

        :Parameters:
          - `username` (string): username to use for authenticating with the
            MongoDB Atlas API. This is the Public Key part of the programmatic
            API key generated via the Atlas Web UI.
          - `password` (string): password to use for authenticating with the
            MongoDB Atlas API. This is the Private Key part of the programmatic
            API key generated via the Atlas Web UI.
          - `base_url` (string, optional): base URL to use for
            communicating with the MongoDB Atlas API.
            Default: https://cloud.mongodb.com/api/atlas.
          - `api_version` (float, optional): version of the Atlas API to
            use while issuing requests. Default: 1.0.
          - `timeout` (float, optional): time, in seconds, after which an
            HTTP request to the Atlas API should timeout. Default: 10.0.
          - `verbose` (int, optional): logging level. Default: 0.
        """
        config = get_client_configuration(
            base_url=base_url,
            api_version=api_version,
            username=username,
            password=password,
            timeout=timeout,
            verbose=verbose)
        return cls(config)

    def __getattr__(self, path):
        return _ApiComponent(self, path)

    @property
    def root(self):
        """
        Access the root resource of the Atlas API.

        This needs special handling because empty paths are not otherwise
        supported by the Fluent API implementation.
        """
        return _ApiComponent(self, '')

    def request(self, method, path, **params):
        """
        Issue an HTTP request and process the response.

        :Parameters:
          - `method` (string): HTTP method to use for issuing the request.
          - `path` (string): path of the resource (relative to the API's
            base URL) against which to issue the request.
          - `params` (dict): query and body parameters to use for the request.
            Currently, only the "pretty", "envelope", "itemsPerPage", and
            "pageNum" query parameters are supported and all other parameters
            are passed as body parameters. Users may use the "json" kwarg to
            specify raw JSON input. This is useful when a user needs to send a
            payload that does not consist of key-value pairs (e.g. when adding
            a server to the IP Whitelist, a list of documents must be sent).
        """
        method = method.upper()
        url = self.construct_resource_url(path)

        query_params = {}
        for param_name in ("pretty", "envelope", "itemsPerPage", "pageNum"):
            if param_name in params:
                query_params[param_name] = params.pop(param_name)

        raw_json = params.pop('json', None)
        if raw_json:
            params = raw_json

        request_kwargs = {
            'auth': self.config.auth,
            'params': query_params,
            'json': params,
            'timeout': self.config.timeout}

        try:
            response = requests.request(method, url, **request_kwargs)
        except requests.RequestException as e:
            raise AtlasClientError(
                str(e),
                resource_url=url,
                request_method=method
            )

        return self.handle_response(method, response)

    def construct_resource_url(self, path):
        url_template = "{base_url}/v{version}/{resource_path}"
        return url_template.format(base_url=self.config.base_url,
                                   version=self.config.api_version,
                                   resource_path=path)

    @staticmethod
    def handle_response(method, response):
        try:
            data = response.json(object_hook=JSONObject)
        except ValueError:
            data = None

        if response.status_code in (200, 201, 202):
            return _ApiResponse(response, method, data)

        if response.status_code == 429:
            raise AtlasRateLimitError('Too many requests', response=response,
                                      request_method=method, error_code=429)

        if data is None:
            raise AtlasApiError('Unable to decode JSON response.',
                                response=response, request_method=method)

        atlas_error_code = data.get('errorCode')
        kwargs = {
            'response': response,
            'request_method': method,
            'error_code': atlas_error_code}

        if response.status_code == 400:
            raise AtlasApiError('400: Bad Request.', **kwargs)

        if response.status_code == 401:
            raise AtlasAuthenticationError('401: Unauthorized.', **kwargs)

        if response.status_code == 403:
            raise AtlasApiError('403: Forbidden.', **kwargs)

        if response.status_code == 404:
            raise AtlasApiError('404: Not Found.', **kwargs)

        if response.status_code == 409:
            raise AtlasApiError('409: Conflict.', **kwargs)

        raise AtlasApiError(
            'An unknown error occurred processing your request.', **kwargs)
