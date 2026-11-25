"""Dialog pilih/simpan file INAA (pembungkus Gtk.FileDialog / Gtk.FileChooserNative).

Kenapa bukan `Gtk.FileChooserDialog`: di sebagian lingkungan (teramati: GTK 4.22.4 +
cairo 1.18.4, KDE/Wayland) dialog itu meng-abort seluruh proses dengan
`cairo_surface_set_device_scale: Assertion status == CAIRO_STATUS_SUCCESS failed`,
apa pun tema GTK, tema ikon, atau renderer-nya. `Gtk.FileDialog` (GTK >= 4.10) dan
`Gtk.FileChooserNative` tidak crash di lingkungan yang sama.

Semua fungsi memanggil callback hanya bila pengguna benar-benar memilih sesuatu, dan
hanya dengan path lokal (berkas non-lokal diabaikan, seperti perilaku lama).
"""
from gi.repository import Gio, GLib, Gtk

# Jaga referensi dialog native sampai responsnya datang (kalau tidak, bisa dibuang GC).
_PENDING = set()


def _make_filter(patterns, name):
    flt = Gtk.FileFilter()
    flt.set_name(name or ", ".join(patterns))
    for pattern in patterns:
        flt.add_pattern(pattern)
    return flt


def _paths_from_model(model):
    """Daftar path lokal dari Gio.ListModel berisi Gio.File."""
    paths = []
    if model is None:
        return paths
    for i in range(model.get_n_items()):
        gfile = model.get_item(i)
        path = gfile.get_path() if gfile is not None else None
        if path:
            paths.append(path)
    return paths


def pick_files(
    parent, title, on_paths, *, multiple=False, patterns=None, pattern_name=None, include_all=False
):
    """Pilih satu/banyak file. `on_paths(list[str])` dipanggil bila ada pilihan.

    `include_all=True` menambahkan filter "Semua Berkas" di samping filter `patterns`.
    """
    flt = _make_filter(patterns, pattern_name) if patterns else None
    all_flt = None
    if include_all:
        all_flt = Gtk.FileFilter()
        all_flt.set_name("Semua Berkas")
        all_flt.add_pattern("*")

    if hasattr(Gtk, "FileDialog"):  # GTK >= 4.10
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        dialog.set_modal(True)
        if flt is not None:
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(flt)
            if all_flt is not None:
                filters.append(all_flt)
            dialog.set_filters(filters)
            dialog.set_default_filter(flt)

        def done(dlg, result):
            try:
                if multiple:
                    paths = _paths_from_model(dlg.open_multiple_finish(result))
                else:
                    gfile = dlg.open_finish(result)
                    path = gfile.get_path() if gfile is not None else None
                    paths = [path] if path else []
            except GLib.Error:
                return  # dibatalkan / ditutup pengguna
            if paths:
                on_paths(paths)

        if multiple:
            dialog.open_multiple(parent, None, done)
        else:
            dialog.open(parent, None, done)
        return

    native = Gtk.FileChooserNative(
        title=title,
        transient_for=parent,
        action=Gtk.FileChooserAction.OPEN,
        accept_label="_Buka",
        cancel_label="_Batal",
    )
    native.set_modal(True)
    native.set_select_multiple(multiple)
    if flt is not None:
        native.add_filter(flt)
        if all_flt is not None:
            native.add_filter(all_flt)

    def on_response(dlg, response):
        _PENDING.discard(dlg)
        paths = []
        if response == Gtk.ResponseType.ACCEPT:
            paths = _paths_from_model(dlg.get_files())
        dlg.destroy()
        if paths:
            on_paths(paths)

    native.connect("response", on_response)
    _PENDING.add(native)
    native.show()


def pick_save_path(parent, title, on_path, *, initial_name=None):
    """Pilih lokasi simpan. `on_path(str)` dipanggil bila pengguna memilih."""
    if hasattr(Gtk, "FileDialog"):  # GTK >= 4.10
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        dialog.set_modal(True)
        if initial_name:
            dialog.set_initial_name(initial_name)

        def done(dlg, result):
            try:
                gfile = dlg.save_finish(result)
            except GLib.Error:
                return  # dibatalkan / ditutup pengguna
            path = gfile.get_path() if gfile is not None else None
            if path:
                on_path(path)

        dialog.save(parent, None, done)
        return

    native = Gtk.FileChooserNative(
        title=title,
        transient_for=parent,
        action=Gtk.FileChooserAction.SAVE,
        accept_label="_Simpan",
        cancel_label="_Batal",
    )
    native.set_modal(True)
    if initial_name:
        native.set_current_name(initial_name)

    def on_response(dlg, response):
        _PENDING.discard(dlg)
        path = None
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dlg.get_file()
            path = gfile.get_path() if gfile is not None else None
        dlg.destroy()
        if path:
            on_path(path)

    native.connect("response", on_response)
    _PENDING.add(native)
    native.show()
