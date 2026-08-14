"""
Nikka — Custom exception hierarchy.

Provides granular error types so callers can catch specific failures
without resorting to bare ``except Exception``.
"""


class NikkaError(Exception):
    """Base exception for all Nikka errors."""


class UIParseError(NikkaError):
    """Raised when the UI tree cannot be read or parsed."""


class ElementNotFoundError(NikkaError):
    """Raised when an element ID is not in the current state mapping."""

    def __init__(self, element_id: int, valid_ids: list[int] | None = None) -> None:
        self.element_id = element_id
        self.valid_ids = valid_ids or []
        ids_str = f" Valid IDs: {self.valid_ids}." if self.valid_ids else ""
        super().__init__(
            f"Element ID {element_id} not found.{ids_str} "
            "Call get_screen_context() to refresh."
        )


class DesktopError(NikkaError):
    """Raised when a virtual desktop operation fails."""


class AppLaunchError(NikkaError):
    """Raised when an application cannot be started."""
