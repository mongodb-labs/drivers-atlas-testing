import logging

from http.client import HTTPConnection


class JSONObject(dict):
    """Dictionary with dot-notation read access."""
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError('{} has no property named {}}.'.format(
            self.__class__.__name__, name))


def enable_http_logging(loglevel):
    """Enables logging of all HTTP requests."""
    # Enable logging for HTTP Requests and Responses.
    HTTPConnection.debuglevel = loglevel

    # Python logging levels are 0, 10, 20, 30, 40, 50
    py_loglevel = loglevel * 10
    logging.basicConfig()
    logging.getLogger().setLevel(py_loglevel)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(py_loglevel)
    requests_log.propagate = True
