"""Dialog editor pintasan keyboard (Shortcut Editor)."""
from gi.repository import Gdk, Gtk

from keybindings import DEFAULT_SHORTCUTS, SHORTCUT_LABELS, combo_from_event, merge_shortcuts


class ShortcutsMixin:
    """Mixed into PlayerWindow. Owns the shortcut editor dialog."""

    def open_shortcuts_editor(self, _button=None):
        """Dialog visual untuk melihat dan menyunting pintasan keyboard (Shortcut Editor)."""
        dialog = Gtk.Dialog(
            title="Pintasan Keyboard (Shortcuts)",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons(
            "Tutup", Gtk.ResponseType.CLOSE,
        )
        dialog.set_default_size(520, 480)

        content = dialog.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_spacing(10)

        desc = Gtk.Label(label="Klik pada kolom tombol untuk mengubah pintasan aksi yang diinginkan:")
        desc.set_xalign(0)
        desc.add_css_class("dim-label")
        content.append(desc)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.set_child(listbox)
        content.append(scroll)

        # Ambil konfigurasi pintasan saat ini
        active_shortcuts = merge_shortcuts(self._config.get("shortcuts"))

        def update_shortcut(action_key, new_combo):
            current_custom = self._config.get("shortcuts", {})
            if not isinstance(current_custom, dict):
                current_custom = {}
            if new_combo == DEFAULT_SHORTCUTS.get(action_key):
                current_custom.pop(action_key, None)
            else:
                current_custom[action_key] = new_combo
            self._config["shortcuts"] = current_custom
            self._save_config_throttled(force=True)

        for action_key, default_combo in DEFAULT_SHORTCUTS.items():
            label_text = SHORTCUT_LABELS.get(action_key, action_key)
            current_val = active_shortcuts.get(action_key, default_combo)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_margin_top(6)
            row.set_margin_bottom(6)
            row.set_margin_start(8)
            row.set_margin_end(8)

            action_lbl = Gtk.Label(label=label_text)
            action_lbl.set_xalign(0)
            action_lbl.set_hexpand(True)
            row.append(action_lbl)

            combo_btn = Gtk.Button(label=current_val)
            combo_btn.set_size_request(110, -1)
            combo_btn.add_css_class("iina-seg-btn")

            def make_listener(btn, act_k):
                def on_btn_clicked(_b):
                    btn.set_label("Tekan tombol...")
                    key_ctl = Gtk.EventControllerKey()
                    def on_key_capture(c, keyval, keycode, state):
                        name = Gdk.keyval_name(keyval)
                        if not name:
                            return False
                        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
                        alt = bool(state & Gdk.ModifierType.ALT_MASK)
                        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
                        new_c = combo_from_event(name, ctrl=ctrl, alt=alt, shift=shift)
                        if new_c:
                            btn.set_label(new_c)
                            update_shortcut(act_k, new_c)
                            btn.remove_controller(key_ctl)
                            return True
                        return False
                    key_ctl.connect("key-pressed", on_key_capture)
                    btn.add_controller(key_ctl)
                return on_btn_clicked

            combo_btn.connect("clicked", make_listener(combo_btn, action_key))
            row.append(combo_btn)

            listbox.append(row)

        # Tombol Reset ke Default
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_reset_all = Gtk.Button(label="Reset Semua ke Default")
        def on_reset_clicked(_b):
            self._config["shortcuts"] = {}
            self._save_config_throttled(force=True)
            dialog.destroy()
            self.show_toast("Pintasan dikembalikan ke default")
            self.open_shortcuts_editor()
        btn_reset_all.connect("clicked", on_reset_clicked)
        bottom_box.append(btn_reset_all)
        content.append(bottom_box)

        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()

