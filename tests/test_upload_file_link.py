from io import BytesIO
from typing import Any
from uuid import uuid4

import pytest
from aiwardrobe_api.routers.uploads import upload_file
from aiwardrobe_core.config import Settings
from aiwardrobe_core.models import ImageAsset, Upload
from fastapi import UploadFile
from starlette.datastructures import Headers


class UploadSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushes += 1
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid4()

    async def commit(self) -> None:
        return None

    async def refresh(self, _value: Any) -> None:
        return None


async def test_direct_upload_flushes_image_id_before_building_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = UploadSession()

    async def fake_put_bytes(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def fake_enqueue(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr("aiwardrobe_api.routers.uploads.get_settings", lambda: Settings())
    monkeypatch.setattr("aiwardrobe_api.routers.uploads.ObjectStorage.put_bytes", fake_put_bytes)
    monkeypatch.setattr("aiwardrobe_api.routers.uploads.enqueue_upload_with_key", fake_enqueue)
    file = UploadFile(
        file=BytesIO(b"\xff\xd8\xff\xe0" + b"synthetic-jpeg"),
        filename="look.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )

    result = await upload_file(
        file=file,
        selection_json=None,
        upload_type="auto",
        user_id=uuid4(),
        session=session,  # type: ignore[arg-type]
    )

    image = next(value for value in session.added if isinstance(value, ImageAsset))
    upload = next(value for value in session.added if isinstance(value, Upload))
    assert session.flushes == 2
    assert image.id is not None
    assert upload.original_image_id == image.id
    assert result.id == upload.id
