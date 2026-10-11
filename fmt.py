"""Helper pemformatan kecil tanpa dependensi GTK, supaya bisa dites langsung."""


def format_speed(value):
    """Format kecepatan putar untuk label UI: 1.0 -> "1x", 1.5 -> "1.5x", 0.25 -> "0.25x".

    Bug sebelumnya: f"{v:.2f}x".rstrip("0") tidak menghapus nol apa pun karena
    karakter terakhir adalah "x", lalu "x" ditambahkan lagi -> "1.00xx".
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 1.0
    return f"{number:.2f}".rstrip("0").rstrip(".") + "x"
