"""Wayland screen capture using xdg-desktop-portal ScreenCast + PipeWire/GStreamer.

On GNOME Wayland, traditional X11 screenshot methods don't work due to security
restrictions. This module uses the xdg-desktop-portal ScreenCast interface to
request screen sharing permission (one-time user consent), then captures frames
via GStreamer's pipewiresrc element.

Session lifecycle:
    1. create_session() -> user sees GNOME consent dialog (once)
    2. capture_frame() -> fast frame capture via GStreamer
    3. close() -> cleanup session

The session uses persist_mode=2, so the user only needs to approve once until
the permission is explicitly revoked.
"""

from __future__ import annotations

import logging
import os
import random
import string
import sys
import tempfile
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)

# Only available on Linux
_AVAILABLE = sys.platform == "linux"


def _check_deps() -> bool:
    """Check if all required dependencies are available."""
    if not _AVAILABLE:
        return False
    try:
        import gi
        gi.require_version("Gio", "2.0")
        gi.require_version("GLib", "2.0")
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
        # Check for pipewiresrc element
        factory = Gst.ElementFactory.find("pipewiresrc")
        if not factory:
            logger.debug("GStreamer pipewiresrc element not found")
            return False
        return True
    except (ImportError, ValueError) as e:
        logger.debug(f"Wayland capture deps not available: {e}")
        return False


class WaylandScreenCapturer:
    """Captures screenshots on Wayland via xdg-desktop-portal ScreenCast.

    Uses the portal to get a PipeWire stream, then GStreamer to capture
    individual frames. The user approves screen sharing once via GNOME's
    consent dialog.

    Example:
        cap = WaylandScreenCapturer()
        if cap.create_session():
            img = cap.capture_frame()
            region = cap.capture_region(100, 100, 400, 300)
            cap.close()
    """

    def __init__(self):
        self._session_handle: str | None = None
        self._pw_fd: int | None = None
        self._pw_node: int | None = None
        self._bus = None
        self._active = False
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        """Whether a ScreenCast session is established."""
        return self._active and self._pw_fd is not None and self._pw_node is not None

    def create_session(self, timeout_seconds: int = 30) -> bool:
        """Create a ScreenCast session. Shows GNOME consent dialog on first use.

        Args:
            timeout_seconds: Max time to wait for user to approve.

        Returns:
            True if session was established successfully.
        """
        if self._active:
            return True

        try:
            import gi
            gi.require_version("Gio", "2.0")
            gi.require_version("GLib", "2.0")
            from gi.repository import Gio, GLib
        except (ImportError, ValueError) as e:
            logger.warning(f"Cannot create Wayland capture session: {e}")
            return False

        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        except Exception as e:
            logger.warning(f"Cannot connect to session bus: {e}")
            return False

        loop = GLib.MainLoop()
        state = {"step": "create_session", "ok": False}

        def on_response(conn, sender, path, iface, signal, params):
            resp = params.get_child_value(0).get_uint32()
            results = params.get_child_value(1)
            step = state["step"]

            if step == "create_session":
                if resp != 0:
                    logger.warning(f"CreateSession failed: response={resp}")
                    loop.quit()
                    return
                sh = results.lookup_value("session_handle", GLib.VariantType("s"))
                if sh:
                    self._session_handle = sh.get_string()
                GLib.idle_add(_select_sources)

            elif step == "select_sources":
                if resp != 0:
                    logger.warning(f"SelectSources failed: response={resp}")
                    loop.quit()
                    return
                GLib.idle_add(_start_stream)

            elif step == "start":
                if resp != 0:
                    logger.warning(f"Start failed: response={resp} (user may have cancelled)")
                    loop.quit()
                    return
                streams = results.lookup_value("streams", None)
                if streams and streams.n_children() > 0:
                    first = streams.get_child_value(0)
                    self._pw_node = first.get_child_value(0).get_uint32()

                # Open PipeWire remote
                try:
                    fd_result, fd_list = self._bus.call_with_unix_fd_list_sync(
                        "org.freedesktop.portal.Desktop",
                        "/org/freedesktop/portal/desktop",
                        "org.freedesktop.portal.ScreenCast",
                        "OpenPipeWireRemote",
                        GLib.Variant("(oa{sv})", (self._session_handle, {})),
                        GLib.VariantType.new("(h)"),
                        Gio.DBusCallFlags.NONE,
                        5000,
                        None,
                        None,
                    )
                    self._pw_fd = fd_list.get(0)
                    state["ok"] = True
                    logger.info(
                        f"Wayland ScreenCast session ready: "
                        f"fd={self._pw_fd}, node={self._pw_node}"
                    )
                except Exception as e:
                    logger.error(f"OpenPipeWireRemote failed: {e}")
                loop.quit()

        def _select_sources():
            state["step"] = "select_sources"
            opts = GLib.VariantBuilder(GLib.VariantType.new("a{sv}"))
            opts.add_value(GLib.Variant.new_dict_entry(
                GLib.Variant.new_string("types"),
                GLib.Variant.new_variant(GLib.Variant.new_uint32(1)),  # Monitor
            ))
            opts.add_value(GLib.Variant.new_dict_entry(
                GLib.Variant.new_string("multiple"),
                GLib.Variant.new_variant(GLib.Variant.new_boolean(False)),
            ))
            opts.add_value(GLib.Variant.new_dict_entry(
                GLib.Variant.new_string("persist_mode"),
                GLib.Variant.new_variant(GLib.Variant.new_uint32(2)),
            ))
            try:
                self._bus.call_sync(
                    "org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop",
                    "org.freedesktop.portal.ScreenCast",
                    "SelectSources",
                    GLib.Variant.new_tuple(
                        GLib.Variant.new_object_path(self._session_handle),
                        opts.end(),
                    ),
                    GLib.VariantType.new("(o)"),
                    Gio.DBusCallFlags.NONE, 5000, None,
                )
            except Exception as e:
                logger.error(f"SelectSources call failed: {e}")
                loop.quit()

        def _start_stream():
            state["step"] = "start"
            try:
                self._bus.call_sync(
                    "org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop",
                    "org.freedesktop.portal.ScreenCast",
                    "Start",
                    GLib.Variant.new_tuple(
                        GLib.Variant.new_object_path(self._session_handle),
                        GLib.Variant.new_string(""),
                        GLib.Variant.new_array(GLib.VariantType.new("{sv}"), []),
                    ),
                    GLib.VariantType.new("(o)"),
                    Gio.DBusCallFlags.NONE,
                    timeout_seconds * 1000,
                    None,
                )
            except Exception as e:
                logger.error(f"Start call failed: {e}")
                loop.quit()

        # Subscribe to portal Response signals
        sub_id = self._bus.signal_subscribe(
            "org.freedesktop.portal.Desktop",
            "org.freedesktop.portal.Request",
            "Response",
            None,
            None,
            0,  # Gio.DBusSignalFlags.NONE
            on_response,
        )

        # Create session
        try:
            token = "liao_" + "".join(random.choices(string.ascii_lowercase, k=8))
            opts = GLib.VariantBuilder(GLib.VariantType.new("a{sv}"))
            opts.add_value(GLib.Variant.new_dict_entry(
                GLib.Variant.new_string("session_handle_token"),
                GLib.Variant.new_variant(GLib.Variant.new_string(token)),
            ))
            self._bus.call_sync(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.ScreenCast",
                "CreateSession",
                GLib.Variant.new_tuple(opts.end()),
                GLib.VariantType.new("(o)"),
                Gio.DBusCallFlags.NONE, 5000, None,
            )
        except Exception as e:
            logger.error(f"CreateSession call failed: {e}")
            self._bus.signal_unsubscribe(sub_id)
            return False

        GLib.timeout_add_seconds(timeout_seconds + 5, lambda: (loop.quit(), False)[1])
        loop.run()
        self._bus.signal_unsubscribe(sub_id)

        self._active = state["ok"]
        return self._active

    def capture_frame(self) -> "Image | None":
        """Capture a full-screen frame from the ScreenCast session.

        Returns:
            PIL Image or None if capture failed.
        """
        if not self.is_active:
            return None

        with self._lock:
            return self._gst_capture_frame()

    def capture_region(
        self, left: int, top: int, width: int, height: int
    ) -> "Image | None":
        """Capture a region of the screen.

        Args:
            left: Left edge x coordinate.
            top: Top edge y coordinate.
            width: Region width.
            height: Region height.

        Returns:
            Cropped PIL Image or None if capture failed.
        """
        frame = self.capture_frame()
        if frame is None:
            return None
        try:
            return frame.crop((left, top, left + width, top + height))
        except Exception as e:
            logger.error(f"Region crop failed: {e}")
            return None

    def _gst_capture_frame(self) -> "Image | None":
        """Capture a single frame using GStreamer pipewiresrc."""
        try:
            import gi
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
        except (ImportError, ValueError):
            return None

        # Use a temp file for the PNG output
        fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="liao_cap_")
        os.close(fd)

        try:
            pipeline_str = (
                f"pipewiresrc fd={self._pw_fd} path={self._pw_node} do-timestamp=true ! "
                f"videoconvert ! "
                f"pngenc snapshot=true ! "
                f"filesink location={tmp_path}"
            )
            pipeline = Gst.parse_launch(pipeline_str)
            pipeline.set_state(Gst.State.PLAYING)

            gst_bus = pipeline.get_bus()
            msg = gst_bus.timed_pop_filtered(
                8 * Gst.SECOND,
                Gst.MessageType.EOS | Gst.MessageType.ERROR,
            )

            success = False
            if msg and msg.type == Gst.MessageType.EOS:
                success = True
            elif msg and msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                logger.error(f"GStreamer capture error: {err.message}")

            pipeline.set_state(Gst.State.NULL)

            if success and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                from PIL import Image
                img = Image.open(tmp_path).copy()  # .copy() to release file handle
                return img
            return None

        except Exception as e:
            logger.error(f"GStreamer frame capture failed: {e}")
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def close(self):
        """Close the ScreenCast session and release resources."""
        if self._session_handle and self._bus:
            try:
                import gi
                gi.require_version("Gio", "2.0")
                from gi.repository import Gio
                self._bus.call_sync(
                    "org.freedesktop.portal.Desktop",
                    self._session_handle,
                    "org.freedesktop.portal.Session",
                    "Close",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    1000,
                    None,
                )
            except Exception:
                pass
        if self._pw_fd is not None:
            try:
                os.close(self._pw_fd)
            except OSError:
                pass
        self._session_handle = None
        self._pw_fd = None
        self._pw_node = None
        self._active = False
        self._bus = None

    def __del__(self):
        self.close()
