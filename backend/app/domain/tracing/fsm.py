from enum import Enum
from typing import Set, Dict, Optional


class TraceState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"
    CANCEL = "CANCEL"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal FSM state transition is attempted on a Trace."""
    def __init__(self, from_state: str, to_state: str, reason: Optional[str] = None):
        msg = f"Invalid trace state transition from '{from_state}' to '{to_state}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason


class TraceStateMachine:
    """
    Strict 7-State Finite State Machine (FSM) governing Trace lifecycles:
    QUEUED, RUNNING, PARTIAL, COMPLETED, FAILED, RETRY, CANCEL.
    """

    ALLOWED_TRANSITIONS: Dict[TraceState, Set[TraceState]] = {
        TraceState.QUEUED: {TraceState.RUNNING, TraceState.CANCEL, TraceState.FAILED},
        TraceState.RUNNING: {
            TraceState.COMPLETED,
            TraceState.PARTIAL,
            TraceState.RETRY,
            TraceState.FAILED,
            TraceState.CANCEL,
        },
        TraceState.RETRY: {TraceState.RUNNING, TraceState.CANCEL, TraceState.FAILED},
        TraceState.PARTIAL: set(),   # Terminal
        TraceState.COMPLETED: set(), # Terminal
        TraceState.FAILED: set(),    # Terminal
        TraceState.CANCEL: set(),    # Terminal
    }

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        """Return True if transition from from_state to to_state is valid."""
        try:
            source = TraceState(from_state.upper())
            target = TraceState(to_state.upper())
            return target in cls.ALLOWED_TRANSITIONS.get(source, set())
        except ValueError:
            return False

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str, reason: Optional[str] = None) -> None:
        """Validate state transition; raise InvalidStateTransitionError if illegal."""
        if not cls.can_transition(from_state, to_state):
            raise InvalidStateTransitionError(from_state, to_state, reason)

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """Return True if state has no further valid outgoing transitions."""
        try:
            return len(cls.ALLOWED_TRANSITIONS.get(TraceState(state.upper()), set())) == 0
        except ValueError:
            return False
