RETRYABLE_STATUS_CODES: list[int] = [
    408,  # Request Timeout
    429,  # Too Many Requests (after backoff)
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
]
