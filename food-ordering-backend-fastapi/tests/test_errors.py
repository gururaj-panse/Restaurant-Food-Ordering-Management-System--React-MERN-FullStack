"""
Unit test for the OrderOwnershipError class contract
(app/services/restaurant_service.py). Test design and rationale:
docs/testing/unit-test-plan.md §8.
"""

from app.core.errors import AppError, EmptyBodyAppError
from app.services.restaurant_service import OrderOwnershipError


def test_ut_err_01_order_ownership_error_is_an_empty_body_app_error_with_401():
    error = OrderOwnershipError()

    assert isinstance(error, EmptyBodyAppError)
    assert isinstance(error, AppError)
    assert error.status_code == 401
    assert error.message == "unauthorized"
