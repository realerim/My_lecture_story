from PIL import Image, ImageDraw

from lecture_note.capture.screen_watcher import compute_phash, is_changed


def _slide(text: str) -> Image.Image:
    img = Image.new("RGB", (320, 180), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill="black")
    draw.rectangle((20, 60, 120, 140), outline="black", width=3)
    return img


def test_first_frame_always_counts_as_changed():
    h = compute_phash(_slide("slide 1"))
    assert is_changed(None, h, threshold=6) is True


def test_identical_slide_is_not_changed():
    h1 = compute_phash(_slide("slide 1"))
    h2 = compute_phash(_slide("slide 1"))
    assert is_changed(h1, h2, threshold=6) is False


def test_different_slide_text_is_changed():
    h1 = compute_phash(_slide("Chapter 1: Introduction"))
    h2 = compute_phash(_slide("Chapter 9: Conclusion and Q&A"))
    assert is_changed(h1, h2, threshold=6) is True


def test_threshold_controls_sensitivity():
    h1 = compute_phash(_slide("slide 1"))
    h2 = compute_phash(_slide("slide 1!"))
    distance = h2 - h1
    assert is_changed(h1, h2, threshold=distance + 1) is False
    assert is_changed(h1, h2, threshold=max(distance - 1, -1)) is True
