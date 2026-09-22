"""MpvGLArea: the GTK4 GLArea widget that mpv renders video frames into."""
from .common import *  # noqa: F401,F403  (Gtk, GLib, mpv, GObject, ctypes, GL helpers, ...)


class MpvGLArea(Gtk.GLArea):
    """A GTK4 widget that plays video by handing mpv an OpenGL surface."""

    __gsignals__ = {
        "mpv-event": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.set_has_depth_buffer(False)
        self.set_has_stencil_buffer(False)
        self.set_required_version(3, 2)
        self.set_auto_render(False)

        # Allow Desktop GL API if available to ensure full compatibility with libmpv shaders
        if hasattr(self, "set_allowed_apis") and hasattr(Gdk, "GLAPI"):
            try:
                self.set_allowed_apis(Gdk.GLAPI.GL)
            except Exception:
                pass

        self.player = mpv.MPV(
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,       # we draw our own controls
            vo="libmpv",     # render via the libmpv render API, not a native window
            hwdec="auto-safe",
            sub_auto="fuzzy",           # otomatis memuat subtitle dari folder yang sama
            audio_file_auto="fuzzy",     # otomatis memuat audio eksternal jika ada
            ytdl=True,       # enable yt-dlp so URLs (YouTube, etc.) can be played directly
            ytdl_format="bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        )
        self.player.volume = 100
        self._render_ctx = None

        self.connect("realize", self._on_realize)
        self.connect("unrealize", self._on_unrealize)
        self.connect("render", self._on_render)

    def _on_realize(self, area):
        self.make_current()
        self._render_ctx = mpv.MpvRenderContext(
            self.player,
            "opengl",
            opengl_init_params={"get_proc_address": _get_proc_address_wrapper},
        )
        self._render_ctx.update_cb = self._on_mpv_update

    def _on_unrealize(self, area):
        # PENTING: JANGAN terminate() player di sini. `unrealize` juga
        # terpicu saat widget ini dipindah ke top-level window lain (mis.
        # fitur "detach video window") — bukan cuma saat aplikasi ditutup.
        # Kalau mpv di-terminate di sini, saat widget di-realize ulang di
        # window baru kita akan mencoba membuat render context di atas
        # instance mpv yang sudah mati -> segfault. Cukup lepas render
        # context saja; instance mpv tetap hidup dan siap dipakai lagi
        # saat widget di-realize ulang (baik di window yang sama maupun
        # window baru). Mematikan mpv sepenuhnya dilakukan secara terpisah
        # lewat shutdown_player(), dipanggil saat window utama benar-benar
        # ditutup.
        if self._render_ctx:
            self._render_ctx.free()
            self._render_ctx = None

    def shutdown_player(self):
        """Matikan instance mpv sepenuhnya. Panggil ini hanya saat aplikasi
        benar-benar ditutup, bukan saat widget cuma dipindah antar window."""
        if self._render_ctx:
            self._render_ctx.free()
            self._render_ctx = None
        try:
            self.player.terminate()
        except Exception:
            pass

    def _on_mpv_update(self):
        # Called from mpv's internal thread; hop back to the GTK main loop.
        GLib.idle_add(self._request_frame)

    def _request_frame(self):
        if self._render_ctx and self._render_ctx.update():
            self.queue_render()
        return False

    def _on_render(self, area, gl_context):
        if not self._render_ctx:
            return False
        scale = self.get_scale_factor()
        width = self.get_width() * scale
        height = self.get_height() * scale

        # GTK4 GLArea renders into its own internal framebuffer object (FBO).
        # We query the currently bound draw framebuffer so mpv renders into the exact target.
        fbo_val = 0
        if _gl_get_integerv:
            current_fbo = ctypes.c_int(0)
            _gl_get_integerv(GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(current_fbo))
            if current_fbo.value > 0:
                fbo_val = current_fbo.value

        self._render_ctx.render(
            flip_y=True,
            opengl_fbo={"w": width, "h": height, "fbo": fbo_val},
        )
        return True
