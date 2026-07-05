"""Shared image payload validation for API uploads and Telegram transfers."""


class ImageValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def detect_image_content_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image_content(content: bytes, max_bytes: int, allowed_types: set[str]) -> str:
    """Validate raw image bytes and return the detected content type."""
    if len(content) > max_bytes:
        raise ImageValidationError("file_too_large", "Image is too large.")
    detected = detect_image_content_type(content)
    if detected is None:
        raise ImageValidationError("invalid_image", "Uploaded file is not a valid image.")
    if detected not in allowed_types:
        raise ImageValidationError("unsupported_content_type", "Unsupported image content type.")
    return detected
