class AtlasApiException(Exception):
    def __init__(self, msg, resource_url=None, request_method=None,
                 status_code=None, error_code=None, headers=None):
        self._msg = msg
        self.request_method = request_method
        self.resource_url = resource_url
        self.status_code = status_code
        self.error_code = error_code
        self.headers = headers

    def __str__(self):
        if self.request_method and self.resource_url:
            return '{} ({} {})'.format(self._msg, self.request_method,
                                       self.resource_url)
        return self._msg


class AtlasClientError(AtlasApiException):
    pass


class AtlasApiError(AtlasApiException):
    def __init__(self, msg, response=None, request_method=None,
                 error_code=None):
        kwargs = {
            'request_method': request_method,
            'error_code': error_code,
        }
        if response is not None:
            # Parse remaining fields from response object.
            kwargs.update(
                {
                    'status_code': response.status_code,
                    'resource_url': response.url,
                    'headers': response.headers,
                }
            )

        super().__init__(msg, **kwargs)

    def __str__(self):
        if self.request_method and self.resource_url and self.error_code:
            return '{} Error Code: {!r} ({} {})'.format(
                self._msg, self.error_code, self.request_method,
                self.resource_url)
        return super().__str__()


class AtlasRateLimitError(AtlasApiError):
    pass


class AtlasAuthenticationError(AtlasApiError):
    pass
