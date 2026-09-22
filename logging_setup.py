"""
Logging and crash-handling for INAA.

Goals:
  - Every run writes to a rotating log file under ~/.config/inaa/logs/,
    so a bug report can include real diagnostics instead of "it crashed".
  - Uncaught exceptions never dump a raw traceback into a terminal the
    user probably isn't watching (INAA is normally launched from a
    desktop icon) and silently vanish. They get logged with a full
    traceback and, if the GTK toolkit is already available, shown to
    the user as a small error dialog instead of the app just disappearing.
  - This module has ZERO dependency on gi/GTK/mpv so it can be imported
    and initialized as the very first thing in main.py, before we know
    whether those are even installed on this system.

Known limitation (documented honestly rather than silently assumed):
  sys.excepthook reliably catches exceptions raised in the main thread
  outside of GTK's own callback dispatch (startup code, thread targets
  you wrap yourself with the helper below). Exceptions raised *inside*
  a GTK signal handler are caught by sys.excepthook only on newer
  PyGObject versions (which route callback exceptions through it); on
  older PyGObject they are printed by PyGObject directly to stderr and
  do NOT go through this hook or into the log file. If you're on an
  older PyGObject and want every callback exception logged too, wrap
  the callback body in try/except and call log.exception(...) yourself,
  or use the `guard` decorator below for new code.
"""
import logging
import logging.handlers
import sys
import threading
import traceback
from pathlib import Path

LOG_DIR = Path.home() / ".config" / "inaa" / "logs"
LOG_FILE = LOG_DIR / "inaa.log"

_logger = None


def setup_logging(level=logging.INFO):
    """Configure and return the shared 'inaa' logger. Safe to call more
    than once (later calls just return the already-configured logger)."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("inaa")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(threadName)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            LOG_DIR.chmod(0o700)
        except OSError:
            pass
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        try:
            LOG_FILE.chmod(0o600)
        except OSError:
            pass
    except OSError:
        # Disk penuh, home read-only, dsb: jangan sampai gagal setup logging
        # membuat aplikasi gagal start. Konsol tetap dapat log lewat handler
        # di bawah.
        pass

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    logger.info("=== INAA logging dimulai (log file: %s) ===", LOG_FILE)
    _logger = logger
    return logger


def _show_crash_dialog(exc_text):
    """Best-effort: if GTK4 is already importable and a main loop can run,
    show a small dialog with the error. Any failure here is swallowed —
    the log file is always the source of truth, the dialog is a nicety."""
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk, GLib

        def _do_show():
            dialog = Gtk.MessageDialog(
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text="INAA mengalami kesalahan tak terduga",
                secondary_text=(
                    "Detail teknis sudah dicatat ke:\n"
                    f"{LOG_FILE}\n\n"
                    "Silakan lampirkan file itu jika ingin melaporkan bug."
                ),
            )
            dialog.connect("response", lambda d, r: d.destroy())
            dialog.present()
            return False

        GLib.idle_add(_do_show)
    except Exception:
        pass


def install_excepthook(logger):
    """Route uncaught exceptions in the main thread (and any thread created
    via threading.Thread, which does NOT go through sys.excepthook by
    default in Python <3.8-era assumptions worth double-checking) to the
    logger instead of a bare traceback on stderr."""

    def _handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Uncaught exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        _show_crash_dialog(str(exc_value))

    sys.excepthook = _handle

    # threading.excepthook exists since Python 3.8; INAA's thumbnail
    # extraction and subtitle search both run in daemon threads, and
    # exceptions there would otherwise only ever reach the terminal.
    def _thread_handle(args):
        logger.critical(
            "Uncaught exception in thread %s:\n%s",
            args.thread.name if args.thread else "?",
            "".join(
                traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
            ),
        )

    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_handle


def guard(logger=None):
    """Decorator for wrapping a GTK callback so exceptions raised inside it
    are always logged, regardless of PyGObject version behavior. Useful for
    new callbacks; existing ones don't need to be touched immediately."""

    def decorator(fn):
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                log = logger or logging.getLogger("inaa")
                log.exception("Exception in callback %s", getattr(fn, "__name__", fn))
                return None

        wrapper.__name__ = getattr(fn, "__name__", "wrapped")
        return wrapper

    return decorator
