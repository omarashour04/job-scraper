"""
notifier.py — Sends a desktop notification after each scraper run.

Primary method:  win10toast (Windows toast notifications — best on Win 10/11)
Fallback 1:      plyer     (cross-platform, uses system notification APIs)
Fallback 2:      print     (always works, used if all GUI methods fail)

Install on Windows:
    pip install win10toast plyer
"""

import logging
import sys

logger = logging.getLogger(__name__)


def notify(title: str, message: str, duration: int = 12) -> None:
    """
    Show a desktop notification.

    Parameters
    ----------
    title    : str — notification title (bold line)
    message  : str — body text
    duration : int — seconds the notification stays visible (Win10toast only)
    """
    _try_win10toast(title, message, duration)


def _try_win10toast(title: str, message: str, duration: int) -> None:
    """Attempt Windows toast notification via win10toast."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(
            title,
            message,
            duration=duration,
            threaded=True,
        )
        logger.info("Notification sent via win10toast")
        return
    except ImportError:
        logger.debug("win10toast not installed — trying plyer")
    except Exception as exc:
        logger.debug("win10toast failed: %s — trying plyer", exc)

    _try_plyer(title, message)


def _try_plyer(title: str, message: str) -> None:
    """Attempt desktop notification via plyer (cross-platform)."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Job Scraper",
            timeout=12,
        )
        logger.info("Notification sent via plyer")
        return
    except ImportError:
        logger.debug("plyer not installed — falling back to print")
    except Exception as exc:
        logger.debug("plyer notification failed: %s — falling back to print", exc)

    # Final fallback — always visible in terminal / log
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"  {title}")
    print(f"  {message}")
    print(f"{separator}\n")
