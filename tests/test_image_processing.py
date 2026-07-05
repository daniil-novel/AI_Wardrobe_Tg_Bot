from io import BytesIO

import pytest
from aiwardrobe_core.image_processing import ImageProcessingError, create_white_background_product_image
from PIL import Image


def test_create_white_background_product_image_outputs_square_jpeg() -> None:
    source = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    for x in range(8, 32):
        for y in range(4, 16):
            source.putpixel((x, y), (20, 30, 40, 255))
    payload = BytesIO()
    source.save(payload, format="PNG")

    result = create_white_background_product_image(payload.getvalue(), canvas_size=128)

    with Image.open(BytesIO(result)) as output:
        assert output.format == "JPEG"
        assert output.size == (128, 128)
        assert output.getpixel((0, 0)) == (255, 255, 255)


def test_create_white_background_product_image_accepts_rgb_jpeg() -> None:
    source = Image.new("RGB", (20, 40), (12, 80, 140))
    payload = BytesIO()
    source.save(payload, format="JPEG")

    result = create_white_background_product_image(payload.getvalue(), canvas_size=128)

    with Image.open(BytesIO(result)) as output:
        assert output.format == "JPEG"
        assert output.size == (128, 128)


def test_create_white_background_product_image_rejects_invalid_bytes() -> None:
    with pytest.raises(ImageProcessingError):
        create_white_background_product_image(b"not-an-image")
