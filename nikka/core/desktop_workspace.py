"""
Nikka — Virtual Desktop Workspace Manager.

Manages a dedicated virtual desktop for Nikka so she can work independently
without interfering with the user's main desktop. Uses pyvda to create,
find, switch, and track virtual desktops on Windows 10/11.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("nikka.core.desktop_workspace")

# Desktop name that Nikka will use to identify her workspace.
NIKKA_DESKTOP_NAME = "Nikka"


@dataclass
class DesktopWorkspace:
    """
    Singleton-style manager for Nikka's dedicated virtual desktop.

    Tracks which desktop is the user's "origin" and which is Nikka's workspace.
    All pyvda imports are deferred so the rest of Nikka still works if pyvda
    is unavailable.
    """

    _nikka_desktop_number: int | None = field(default=None, repr=False)
    _user_origin_desktop: int | None = field(default=None, repr=False)
    _initialized: bool = field(default=False, repr=False)

    # ── Public API ────────────────────────────────────────────────────────

    def ensure(self) -> int:
        """
        Find or create the "Nikka" desktop and return its desktop number.

        On first call, records the user's current desktop as the origin
        so we can return to it later.

        Returns:
            The 1-indexed desktop number of the Nikka workspace.

        Raises:
            RuntimeError: If pyvda is not installed or the operation fails.
        """
        from pyvda import VirtualDesktop, get_virtual_desktops

        # Record user's current desktop as origin (only on first call)
        if self._user_origin_desktop is None:
            try:
                current = VirtualDesktop.current()
                self._user_origin_desktop = current.number
                logger.info("Recorded user's origin desktop: #%d", self._user_origin_desktop)
            except Exception:
                self._user_origin_desktop = 1
                logger.warning("Could not detect current desktop, defaulting origin to #1")

        # Search for an existing desktop named "Nikka"
        desktops = get_virtual_desktops()
        for d in desktops:
            try:
                if d.name == NIKKA_DESKTOP_NAME:
                    self._nikka_desktop_number = d.number
                    self._initialized = True
                    logger.info("Found existing Nikka desktop: #%d", self._nikka_desktop_number)
                    return self._nikka_desktop_number
            except Exception:
                # .name may fail on some Windows builds; skip and continue
                continue

        # No existing desktop found — create one
        logger.info("Creating new virtual desktop for Nikka...")
        new_desktop = VirtualDesktop.create()
        time.sleep(0.3)

        try:
            new_desktop.rename(NIKKA_DESKTOP_NAME)
            logger.info("Renamed new desktop to '%s'", NIKKA_DESKTOP_NAME)
        except Exception as exc:
            logger.warning("Could not rename desktop (non-critical): %s", exc)

        # Refresh the list to get the correct number
        desktops = get_virtual_desktops()
        self._nikka_desktop_number = len(desktops)  # new desktop is always last
        self._initialized = True
        logger.info("Nikka desktop created as #%d (of %d total)", self._nikka_desktop_number, len(desktops))
        return self._nikka_desktop_number

    def switch_to_nikka(self) -> str:
        """
        Switch to Nikka's workspace desktop.

        Returns:
            Status message describing the result.
        """
        from pyvda import VirtualDesktop

        if not self._initialized or self._nikka_desktop_number is None:
            self.ensure()

        # Record user's current desktop before switching (update origin)
        try:
            current = VirtualDesktop.current()
            if current.number != self._nikka_desktop_number:
                self._user_origin_desktop = current.number
        except Exception:
            pass

        try:
            VirtualDesktop(self._nikka_desktop_number).go()
            time.sleep(0.5)
            return (
                f"Switched to Nikka's workspace (desktop #{self._nikka_desktop_number}). "
                f"User's desktop is #{self._user_origin_desktop}."
            )
        except Exception as exc:
            logger.error("Failed to switch to Nikka desktop: %s", exc)
            # Desktop may have been removed externally — re-create
            self._initialized = False
            self._nikka_desktop_number = None
            self.ensure()
            VirtualDesktop(self._nikka_desktop_number).go()
            time.sleep(0.5)
            return (
                f"Re-created and switched to Nikka's workspace (desktop #{self._nikka_desktop_number})."
            )

    def switch_to_user(self) -> str:
        """
        Switch back to the user's original desktop.

        Returns:
            Status message describing the result.
        """
        from pyvda import VirtualDesktop

        target = self._user_origin_desktop or 1
        try:
            VirtualDesktop(target).go()
            time.sleep(0.5)
            return f"Returned to user's desktop (#{target})."
        except Exception as exc:
            logger.error("Failed to return to user desktop #%d: %s", target, exc)
            # Fallback to desktop 1
            try:
                VirtualDesktop(1).go()
                time.sleep(0.5)
                return "Returned to desktop #1 (fallback)."
            except Exception as fallback_exc:
                return f"Failed to return to user desktop: {fallback_exc}"

    def get_info(self) -> dict:
        """
        Return current workspace state information.

        Returns:
            Dict with keys: nikka_desktop, user_desktop, current_desktop,
            total_desktops, is_on_nikka_desktop, initialized.
        """
        from pyvda import VirtualDesktop, get_virtual_desktops

        try:
            current = VirtualDesktop.current().number
        except Exception:
            current = None

        try:
            total = len(get_virtual_desktops())
        except Exception:
            total = None

        return {
            "nikka_desktop": self._nikka_desktop_number,
            "user_desktop": self._user_origin_desktop,
            "current_desktop": current,
            "total_desktops": total,
            "is_on_nikka_desktop": (
                current == self._nikka_desktop_number
                if current is not None and self._nikka_desktop_number is not None
                else None
            ),
            "initialized": self._initialized,
        }

    @property
    def nikka_desktop_number(self) -> int | None:
        """The 1-indexed number of Nikka's desktop, or None if not yet created."""
        return self._nikka_desktop_number

    @property
    def user_desktop_number(self) -> int | None:
        """The 1-indexed number of the user's origin desktop."""
        return self._user_origin_desktop


# ── Module-level singleton ────────────────────────────────────────────────────
workspace = DesktopWorkspace()
