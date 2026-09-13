import enum
import time
import random
import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("crypto_tracer.circuit_breaker")


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    3-State Circuit Breaker (CLOSED, OPEN, HALF_OPEN) with jittered exponential backoff.
    Protects downstream blockchain nodes and external APIs from cascading failures.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_trials: int = 2,
        backoff_factor: float = 2.0,
        max_recovery_timeout: float = 300.0,
        jitter_ratio: float = 0.2,
    ):
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.base_recovery_timeout = max(0.1, recovery_timeout)
        self.half_open_trials = max(1, half_open_trials)
        self.backoff_factor = max(1.0, backoff_factor)
        self.max_recovery_timeout = max_recovery_timeout
        self.jitter_ratio = max(0.0, min(0.5, jitter_ratio))

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_opens = 0
        self._half_open_successes = 0
        self._last_state_change = time.monotonic()
        self._current_timeout = self.base_recovery_timeout
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state, automatically evaluating OPEN timeout expiration."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_state_change
            if elapsed >= self._current_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        """Check whether a request is allowed through the circuit breaker."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        elif current == CircuitState.HALF_OPEN:
            return self._half_open_successes < self.half_open_trials
        return False

    def get_remaining_cooldown(self) -> float:
        """Remaining seconds before OPEN circuit transitions to HALF_OPEN."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_state_change
            remaining = self._current_timeout - elapsed
            return max(0.0, remaining)
        return 0.0

    async def record_success(self):
        """Record a successful execution through the circuit breaker."""
        async with self._lock:
            current = self.state
            if current == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_trials:
                    self._transition_to(CircuitState.CLOSED)
                    logger.info(
                        f"CircuitBreaker[{self.name}] recovered to CLOSED after "
                        f"{self._half_open_successes} successful probes."
                    )
            elif current == CircuitState.CLOSED:
                self._consecutive_failures = 0

    async def record_failure(self, error: Optional[Exception] = None):
        """Record a failed execution through the circuit breaker."""
        async with self._lock:
            self._consecutive_failures += 1
            current = self.state

            if current == CircuitState.HALF_OPEN:
                self._consecutive_opens += 1
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"CircuitBreaker[{self.name}] probe failed ({error}). "
                    f"Tripped back to OPEN (incident #{self._consecutive_opens})."
                )
            elif current == CircuitState.CLOSED:
                if self._consecutive_failures >= self.failure_threshold:
                    self._consecutive_opens += 1
                    self._transition_to(CircuitState.OPEN)
                    logger.warning(
                        f"CircuitBreaker[{self.name}] reached {self._consecutive_failures} failures. "
                        f"Tripped to OPEN (cooldown={self._current_timeout:.2f}s)."
                    )

    def _transition_to(self, new_state: CircuitState):
        self._state = new_state
        self._last_state_change = time.monotonic()
        if new_state == CircuitState.OPEN:
            raw_timeout = min(
                self.base_recovery_timeout * (self.backoff_factor ** max(0, self._consecutive_opens - 1)),
                self.max_recovery_timeout,
            )
            if self.jitter_ratio > 0:
                jitter_range = raw_timeout * self.jitter_ratio
                jitter = random.uniform(-jitter_range, jitter_range)
                self._current_timeout = max(0.1, raw_timeout + jitter)
            else:
                self._current_timeout = max(0.1, raw_timeout)
            self._half_open_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._consecutive_opens = 0
            self._half_open_successes = 0
            self._current_timeout = self.base_recovery_timeout
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_successes = 0

    def reset(self):
        """Forcibly reset the circuit breaker to CLOSED state."""
        self._transition_to(CircuitState.CLOSED)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_opens": self._consecutive_opens,
            "remaining_cooldown_seconds": round(self.get_remaining_cooldown(), 2),
            "current_timeout_seconds": round(self._current_timeout, 2),
        }
