import unittest
from unittest.mock import patch

from gateway.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker(unittest.TestCase):

    def test_initial_state_is_closed(self):
        breaker = CircuitBreaker()

        self.assertEqual(breaker.state, CircuitState.CLOSED)
        self.assertTrue(breaker.before_request())

    def test_opens_after_failure_threshold(self):
        breaker = CircuitBreaker(failure_threshold=3)

        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.CLOSED)

        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.CLOSED)

        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.OPEN)
        self.assertFalse(breaker.before_request())

    def test_open_state_blocks_requests_before_timeout(self):
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=10
        )

        with patch("gateway.circuit_breaker.time.monotonic", return_value=100):
            breaker.record_failure()

        with patch("gateway.circuit_breaker.time.monotonic", return_value=105):
            self.assertFalse(breaker.before_request())

        self.assertEqual(breaker.state, CircuitState.OPEN)

    def test_half_open_allows_only_one_probe(self):
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=10
        )

        with patch("gateway.circuit_breaker.time.monotonic", return_value=100):
            breaker.record_failure()

        with patch("gateway.circuit_breaker.time.monotonic", return_value=111):
            self.assertTrue(breaker.before_request())
            self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

            # Второй запрос не должен пройти, пока проверка не завершилась.
            self.assertFalse(breaker.before_request())

    def test_success_after_probe_closes_breaker(self):
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=10
        )

        with patch("gateway.circuit_breaker.time.monotonic", return_value=100):
            breaker.record_failure()

        with patch("gateway.circuit_breaker.time.monotonic", return_value=111):
            self.assertTrue(breaker.before_request())

        breaker.record_success()

        self.assertEqual(breaker.state, CircuitState.CLOSED)
        self.assertEqual(breaker.failure_count, 0)
        self.assertTrue(breaker.before_request())

    def test_failure_after_probe_reopens_breaker(self):
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=10
        )

        with patch("gateway.circuit_breaker.time.monotonic", return_value=100):
            breaker.record_failure()

        with patch("gateway.circuit_breaker.time.monotonic", return_value=111):
            self.assertTrue(breaker.before_request())
            breaker.record_failure()

            self.assertEqual(breaker.state, CircuitState.OPEN)
            self.assertFalse(breaker.before_request())


if __name__ == "__main__":
    unittest.main()
