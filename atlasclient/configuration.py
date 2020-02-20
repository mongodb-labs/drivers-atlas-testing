from collections import namedtuple

from requests.auth import HTTPDigestAuth

from atlasclient.exceptions import AtlasClientError

_Configuration = namedtuple(
    "AtlasClientConfiguration",
    ["base_url", "api_version", "auth", "timeout", "verbose"])


# Default configuration values.
_DEFAULT_HTTP_TIMEOUT = 10
_DEFAULT_API_VERSION = 1.0
_DEFAULT_BASE_URL = "https://cloud.mongodb.com/api/atlas"


def get_client_configuration(*, base_url, api_version, username,
                             password, timeout, verbose):
    if not username or not password:
        raise ValueError("Username and/or password cannot be empty.")

    config = _Configuration(
        base_url=base_url or _DEFAULT_BASE_URL,
        api_version=api_version or _DEFAULT_API_VERSION,
        auth=HTTPDigestAuth(username=username,
                            password=password),
        timeout=timeout or _DEFAULT_HTTP_TIMEOUT,
        verbose=verbose)
    return config
