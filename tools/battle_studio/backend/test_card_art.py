from card_art import _images, _normalize_number


def test_normalize_collection_number() -> None:
    assert _normalize_number("004/198") == "4198"
    assert _normalize_number("004") == "4"


def test_images_prefers_small_and_keeps_large() -> None:
    assert _images({"id": "sv1-1", "images": {"small": "https://example/s.png", "large": "https://example/l.png"}}) == {
        "small": "https://example/s.png",
        "large": "https://example/l.png",
        "providerId": "sv1-1",
    }
