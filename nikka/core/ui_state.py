"""
Nikka — UI State Manager.

Maintains the ephemeral mapping from sequential integer IDs to screen
coordinates.  This is the heart of the anti-hallucination strategy:
the LLM only sees IDs, never raw pixel coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UIElement:
    """A single interactive UI element discovered from pywinauto."""

    element_id: int
    control_type: str
    name: str
    rect: tuple[int, int, int, int]  # (left, top, right, bottom)
    center_x: int
    center_y: int
    is_enabled: bool = True
    automation_id: str = ""
    value: str = ""  # current value for edit boxes, combo boxes, etc.

    def __repr__(self) -> str:
        return (
            f"UIElement(id={self.element_id}, type='{self.control_type}', "
            f"name='{self.name}', center=({self.center_x}, {self.center_y}))"
        )


@dataclass
class UIStateManager:
    """
    Singleton-style state that maps integer IDs → :class:`UIElement` instances.

    Rebuilt from scratch on every call to ``get_screen_context()``.
    Thread-safety is *not* required — the agent operates sequentially.
    """

    elements: dict[int, UIElement] = field(default_factory=dict)
    _next_id: int = 1
    window_title: str = ""

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all tracked elements and reset the ID counter."""
        self.elements.clear()
        self._next_id = 1
        self.window_title = ""

    # ── Registration ───────────────────────────────────────────────────────

    def register(self, element: UIElement) -> int:
        """Assign the next sequential ID to *element* and store it.

        Returns:
            The newly assigned integer ID.
        """
        element.element_id = self._next_id
        self.elements[self._next_id] = element
        self._next_id += 1
        return element.element_id

    # ── Lookup ─────────────────────────────────────────────────────────────

    def lookup(self, element_id: int) -> Optional[UIElement]:
        """Return the element for *element_id*, or ``None`` if not found."""
        return self.elements.get(element_id)

    @property
    def valid_ids(self) -> list[int]:
        """Sorted list of currently registered element IDs."""
        return sorted(self.elements.keys())

    @property
    def count(self) -> int:
        """Number of currently registered elements."""
        return len(self.elements)


# ── Module-level singleton shared across all tool invocations ──────────────
ui_state = UIStateManager()
