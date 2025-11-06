import multiprocessing

import pytest
from pytest_httpserver import HTTPServer
from requests.exceptions import RetryError

from common.config.project import HTTPConfig
from common.util.http.client import BaseClient
from common.util.http.exceptions import ClientError


@pytest.mark.parametrize(
    "http_config,method,expected_error,status_code",
    [
        # should not
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "POST", True, 200),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", True, 200),
        # should not repeat on 404
        (
            HTTPConfig(timeout="PT5S", retries=2, backoff_factor=1),
            "POST",
            ClientError,
            404,
        ),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", ClientError, 404),
        # tests for status codes from RETRYABLE_STATUS_CODES
        # Request Timeout
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "POST", RetryError, 408),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", RetryError, 408),
        # Too Many Requests (after backoff)
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "POST", RetryError, 429),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", RetryError, 429),
        # Internal Server Error
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "POST", RetryError, 500),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", RetryError, 500),
        # Bad Gateway
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "POST", RetryError, 502),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", RetryError, 502),
        # Service Unavailable
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "POST", RetryError, 503),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", RetryError, 503),
        # Gateway Timeout
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "POST", RetryError, 504),
        (HTTPConfig(timeout=5, retries=2, backoff_factor=1), "GET", RetryError, 504),
    ],
)
def test_base_client_get(
    httpserver: HTTPServer,
    http_config: HTTPConfig,
    method: str,
    expected_error: Exception | bool,
    status_code: int,
):
    """
    Tests behaviour of BaseClient with different http configurations.
        For status codes listed in {``RETRYABLE_STATUS_CODES``} the API calls should be repeated.
    :param httpserver:
    :param http_config:
    :param expected_error:
    :param status_code:
    :return:
    """
    httpserver.expect_request("/fhir/").respond_with_json(
        response_json='{"error": "not found"}', status=status_code
    )

    client = BaseClient(httpserver.url_for(""), http_config=http_config)

    if method == "GET":
        if isinstance(expected_error, type) and issubclass(expected_error, Exception):
            with pytest.raises(expected_error):
                client.get("fhir/")
        else:
            assert client.get("fhir/") is not None
    elif method == "POST":
        if isinstance(expected_error, type) and issubclass(expected_error, Exception):
            with pytest.raises(expected_error):
                client.post("fhir/", body="{}")
        else:
            assert client.post("fhir/", body="{}") is not None


@pytest.mark.parametrize(
    "http_config,method,status_code",
    [
        (HTTPConfig(timeout=5, retries=None, backoff_factor=1), "POST", 500),
        (HTTPConfig(timeout=5, retries=None, backoff_factor=1), "GET", 500),
    ],
)
def test_infinite_base_client(
    httpserver: HTTPServer,
    http_config: HTTPConfig,
    method: str,
    status_code: int,
):
    """
    Tests whether the API call keeps repeating at least for 2 minutes.
        Keep in mind these API calls should continue indefinitely for
        status code from the {``RETRYABLE_STATUS_CODES``}
    :param httpserver: HTTPServer - fixture from pytest-httpserver
    :param http_config: HTTPConfig - case which should be tested
    :param status_code: response status code from httpserver
    :return:
    """
    httpserver.expect_request("/fhir/").respond_with_json(
        response_json='{"error": "not found"}', status=status_code
    )

    client = BaseClient(httpserver.url_for(""), http_config=http_config)

    p: multiprocessing.Process | None = None
    if method == "GET":
        p = multiprocessing.Process(target=client.get, args=["fhir/"])
    elif method == "POST":
        p = multiprocessing.Process(
            target=client.post, kwargs={"context_path": "fhir/", "body": "{}"}
        )

    if p is not None:
        p.start()
        p.join(timeout=10)
        if p.is_alive():
            p.terminate()
            p.join()
            assert True
            return

    assert False  # if test exited before timer runs out
