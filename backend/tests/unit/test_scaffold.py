"""Smoke test: proves pytest can discover and run tests."""


def test_pytest_runs() -> None:
    assert True


def test_response_model_ok() -> None:
    from app.core.response import ResponseModel

    r = ResponseModel.ok({"key": "value"})
    assert r.status == "success"
    assert r.data == {"key": "value"}
    assert r.error is None
    assert r.request_id != ""


def test_response_model_fail() -> None:
    from app.core.errors import AUTH_FORBIDDEN
    from app.core.response import ResponseModel

    r = ResponseModel.fail(AUTH_FORBIDDEN, "Доступ запрещён")
    assert r.status == "error"
    assert r.data is None
    assert r.error is not None
    assert r.error.code == AUTH_FORBIDDEN


def test_error_codes_exist() -> None:
    import app.core.errors as e

    required = [
        "AUTH_INVALID_CREDENTIALS",
        "AUTH_FORBIDDEN",
        "SCENARIO_NOT_VALID",
        "SESSION_NOT_READY",
        "HINT_LIMIT_EXCEEDED",
        "VERIFICATION_FAILED",
        "LLM_PROVIDER_UNAVAILABLE",
        "SANDBOX_LIMIT_EXCEEDED",
        "REPORT_PERIOD_REQUIRED",
        "VALIDATION_ERROR",
    ]
    for code in required:
        assert hasattr(e, code), f"Missing error code: {code}"
