import requests

from atlasclient.configuration import get_client_configuration
from atlasclient.exceptions import (
    AtlasClientError, AtlasApiError, AtlasRateLimitError)
from atlasclient.utils import enable_http_logging, JSONObject


_EMPTY_PATH_ERR_MSG_TEMPLATE = ('Calling {} on an empty API path is not '
                                'supported.')


class ApiComponent:
    def __init__(self, client, path=None):
        self._client = client
        self._path = path

    def __repr__(self):
        return '<ApiComponent: %s>' % self._path

    def __getitem__(self, path):
        if self._path is not None:
            path = '%s/%s' % (self._path, path)
        return ApiComponent(self._client, path)

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


class ApiResponse:
    def __init__(self, response, request_method, json_data):
        self.resource_url = response.url
        self.headers = response.headers
        self.request_method = request_method
        self.data = json_data

    def __repr__(self):
        return '<{}: {} {}>'.format(self.__class__.__name__,
                                     self.request_method, self.resource_url)


class AtlasClient:
    def __init__(self, config):
        self.config = config
        if config.verbose:
            enable_http_logging(config.verbose)

    @classmethod
    def from_configuration_options(cls, *, base_url, api_version, username,
                                   password, timeout=None, verbose=None):
        config = get_client_configuration(
            base_url=base_url,
            api_version=api_version,
            username=username,
            password=password,
            timeout=timeout,
            verbose=verbose)
        return cls(config)

    def __getattr__(self, path):
        return ApiComponent(self, path)

    @property
    def root(self):
        """Access the root resource of the Atlas API.

        This needs special handling because empty paths are not generally
        supported by the Fluent API.
        """
        return ApiComponent(self, '')

    def request(self, method, path, **params):
        method = method.upper()
        url = self.construct_resource_url(path)

        query_params = {}
        for param_name in ("pretty", "envelope", "itemsPerPage", "pageNum"):
            if param_name in params:
                query_params[param_name] = params.pop(param_name)

        raw_json = params.pop('json')
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
            return ApiResponse(response, method, data)

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
            raise AtlasApiError('401: Unauthorized.', **kwargs)

        if response.status_code == 403:
            raise AtlasApiError('403: Forbidden.', **kwargs)

        if response.status_code == 404:
            raise AtlasApiError('404: Not Found.', **kwargs)

        if response.status_code == 40:
            raise AtlasApiError('409: Conflict.', **kwargs)

        raise AtlasApiError(
            'An unknown error has occured processing your request.', **kwargs)
