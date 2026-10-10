"""
Circuit Breaker Pattern Implementation for Enrollment & Saga Service.
Provides fault tolerance and resilience across downstream microservices:
- Student Service
- Course Service
- Fee Service

States:
- CLOSED: Requests pass through normally. Tracks failures.
- OPEN: Failure threshold reached. Fails fast immediately with graceful fallback.
- HALF-OPEN: Recovery timeout elapsed. Allows probe requests to test service recovery.
"""

import time
import threading
from typing import Dict, Any, Tuple, Optional


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    def __init__(self, service_name: str, message: str = ""):
        self.service_name = service_name
        self.message = message or f"Circuit breaker is OPEN for {service_name}. Requests fail fast."
        super().__init__(self.message)


class CircuitBreaker:
    """
    Thread-safe Circuit Breaker implementing CLOSED, OPEN, and HALF-OPEN states.
    """

    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF-OPEN"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 10.0,
        success_threshold: int = 1
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change: float = time.time()
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            # Check if recovery timeout has expired for OPEN state
            if self._state == self.STATE_OPEN and self._last_failure_time is not None:
                if (time.time() - self._last_failure_time) >= self.recovery_timeout:
                    self._state = self.STATE_HALF_OPEN
                    self._last_state_change = time.time()
                    self._success_count = 0
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def can_execute(self) -> Tuple[bool, str]:
        """
        Check if a request is allowed to execute.
        Returns: (is_allowed, reason_or_message)
        """
        current_state = self.state  # triggers timeout check
        with self._lock:
            if current_state == self.STATE_CLOSED:
                return True, "Circuit is CLOSED; request allowed."
            elif current_state == self.STATE_HALF_OPEN:
                return True, "Circuit is HALF-OPEN; probe request allowed."
            else:  # OPEN
                remaining = max(0.0, self.recovery_timeout - (time.time() - (self._last_failure_time or time.time())))
                return False, f"Circuit breaker is OPEN for {self.name}. Requests rejected immediately. Retry in {remaining:.1f}s."

    def record_success(self):
        """Record a successful downstream call."""
        with self._lock:
            if self._state == self.STATE_HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = self.STATE_CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._last_state_change = time.time()
                    self._last_error = None
            elif self._state == self.STATE_CLOSED:
                self._failure_count = 0
                self._last_error = None

    def record_failure(self, error: Optional[str] = None):
        """Record a failed downstream call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._last_error = str(error) if error else "Downstream service error"

            if self._state == self.STATE_HALF_OPEN:
                # Probe failed, return directly to OPEN
                self._state = self.STATE_OPEN
                self._last_state_change = time.time()
                self._success_count = 0
            elif self._state == self.STATE_CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = self.STATE_OPEN
                    self._last_state_change = time.time()

    def reset(self):
        """Manually reset the circuit breaker back to CLOSED state."""
        with self._lock:
            self._state = self.STATE_CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._last_error = None
            self._last_state_change = time.time()

    def trip(self, reason: str = "Manually triggered for demonstration"):
        """Manually trip the circuit breaker into OPEN state."""
        with self._lock:
            self._state = self.STATE_OPEN
            self._failure_count = self.failure_threshold
            self._last_failure_time = time.time()
            self._last_error = reason
            self._last_state_change = time.time()

    def get_status(self) -> Dict[str, Any]:
        """Return the current status dictionary."""
        current_state = self.state
        with self._lock:
            return {
                "state": current_state,
                "failure_count": self._failure_count,
                "threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "last_error": self._last_error,
            }
