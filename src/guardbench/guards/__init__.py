"""Guard adapters behind one interface."""

from guardbench.guards.base import Guard, GuardUnavailableError, Verdict

__all__ = ["Guard", "GuardUnavailableError", "Verdict"]
