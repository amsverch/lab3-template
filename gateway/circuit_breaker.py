import threading
import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=10):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.lock = threading.Lock()
        self.half_open_request = False

    def before_request(self):
        with self.lock:
            if self.state == CircuitState.OPEN:
                elapsed = time.monotonic() - self.last_failure_time

                if elapsed < self.recovery_timeout:
                    return False

                self.state = CircuitState.HALF_OPEN
                self.half_open_request = True
                return True

            if self.state == CircuitState.HALF_OPEN:
                return False

            return True

    def record_success(self):
        with self.lock:
            self.failure_count = 0
            self.last_failure_time = None
            self.state = CircuitState.CLOSED
            self.half_open_request = False

    def record_failure(self):
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            self.half_open_request = False

            if (
                self.failure_count >= self.failure_threshold
                or self.state == CircuitState.HALF_OPEN
            ):
                self.state = CircuitState.OPEN
