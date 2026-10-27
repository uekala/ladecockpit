import logging

import app.main  # noqa: F401 – configures logging on import


def _access_record(path: str) -> logging.LogRecord:
    # Same shape as uvicorn's access log: client, method, path, HTTP version, status.
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:50000", "GET", path, "1.1", 200), None,
    )


def test_http_requests_are_not_logged():
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_health_check_left_out_of_access_log():
    filters = logging.getLogger("uvicorn.access").filters
    assert not all(f.filter(_access_record("/healthz")) for f in filters)
    assert all(f.filter(_access_record("/api/dashboard")) for f in filters)
