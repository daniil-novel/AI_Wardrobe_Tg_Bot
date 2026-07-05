from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageProcessingError(ValueError):
    """Raised when an uploaded image cannot be normalized for product display."""


def create_white_background_product_image(content: bytes, *, canvas_size: int = 1024) -> bytes:
    """Normalize a wardrobe photo into a square JPEG on a white product background."""
    try:
        with Image.open(BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source)
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                white = Image.new("RGBA", rgba.size, "white")
                white.alpha_composite(rgba)
                image = white.convert("RGB")
            else:
                image = image.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise ImageProcessingError("Cannot read image content.") from exc

    if image.width <= 0 or image.height <= 0:
        raise ImageProcessingError("Image has invalid dimensions.")

    target_size = int(canvas_size * 0.86)
    image.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (canvas_size, canvas_size), "white")
    x = (canvas_size - image.width) // 2
    y = (canvas_size - image.height) // 2
    canvas.paste(image, (x, y))

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=92, optimize=True, progressive=True)
    return output.getvalue()
