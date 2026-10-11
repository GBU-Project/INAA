"""Unit tests untuk audio_filters.py: validasi equalizer 10-band, filter aman, dan efek khusus."""
import unittest

import audio_filters


class TestAudioFilters(unittest.TestCase):
    def test_eq_bands_count(self):
        self.assertEqual(len(audio_filters.EQ_BANDS), 10)
        self.assertEqual(len(audio_filters.EQ_BAND_LABELS), 10)

    def test_clamp_gain(self):
        self.assertEqual(audio_filters.clamp_gain(0.0), 0.0)
        self.assertEqual(audio_filters.clamp_gain(6.0), 6.0)
        self.assertEqual(audio_filters.clamp_gain(-12.0), -12.0)
        self.assertEqual(audio_filters.clamp_gain(15.5), 12.0)
        self.assertEqual(audio_filters.clamp_gain(-30.0), -12.0)
        self.assertEqual(audio_filters.clamp_gain("bad"), 0.0)

    def test_build_equalizer_filter_flat(self):
        flat = [0.0] * 10
        self.assertEqual(audio_filters.build_equalizer_filter(flat), "")

    def test_build_equalizer_filter_custom_bands(self):
        gains = [6.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.5]
        filt = audio_filters.build_equalizer_filter(gains)
        self.assertIn("equalizer=f=31.25:width_type=o:w=1:g=6.0", filt)
        self.assertIn("equalizer=f=16000:width_type=o:w=1:g=3.5", filt)
        # band bernilai 0 dB tidak boleh menambah overhead filter
        self.assertNotIn("f=62.5", filt)

    def test_presets_exist_and_valid(self):
        for preset_name, preset_gains in audio_filters.EQ_PRESETS.items():
            self.assertEqual(len(preset_gains), 10, f"Preset {preset_name} harus memiliki 10 band")
            for g in preset_gains:
                self.assertTrue(-12.0 <= g <= 12.0, f"Gain {g} pada {preset_name} di luar batas -12 s/d 12 dB")

    def test_compose_af_string(self):
        # Flat tanpa efek
        self.assertEqual(audio_filters.compose_af_string([0.0] * 10, "none"), "")

        # Efek khusus nightmode
        af_night = audio_filters.compose_af_string([0.0] * 10, "nightmode")
        self.assertEqual(af_night, "lavfi=[loudnorm=I=-16:TP=-1.5:LRA=11]")

        # Equalizer + nightmode
        bass_gains = audio_filters.EQ_PRESETS["bass_boost"]
        af_comb = audio_filters.compose_af_string(bass_gains, "nightmode")
        self.assertIn("equalizer=f=31.25", af_comb)
        self.assertIn("lavfi=[loudnorm", af_comb)

    def test_invalid_effect_rejected(self):
        # Efek tidak dikenal atau injeksi string berbahaya tidak boleh lolos
        evil_effect = "amovie=/etc/passwd"
        af = audio_filters.compose_af_string([0.0] * 10, evil_effect)
        self.assertEqual(af, "")


if __name__ == "__main__":
    unittest.main()
