from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from aiwardrobe_api.routers import avatar
from aiwardrobe_core.config import Settings
from aiwardrobe_core.enums import ProcessingStatus
from aiwardrobe_core.models import AvatarMeasurement, AvatarProfile, GarmentItem, TryOnItem
from aiwardrobe_core.schemas import AvatarProfileUpdate, TryOnCreate
from fastapi import HTTPException


def result_with(value: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def result_with_many(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value = values
    return result


def profile_for(user_id: UUID, **overrides: object) -> AvatarProfile:
    values: dict[str, object] = {
        "id": uuid4(),
        "user_id": user_id,
        "status": "draft",
        "description": None,
        "neutral_clothing": "fitted_studio_basics",
        "reference_image_id": None,
        "generated_image_id": None,
        "consent_version": None,
        "consented_at": None,
        "revoked_at": None,
        "generation_error": None,
        "generated_at": None,
    }
    values.update(overrides)
    return AvatarProfile(**values)


@pytest.mark.asyncio
async def test_profile_helpers_return_measurements_and_404() -> None:
    user_id = uuid4()
    profile = profile_for(user_id, description="Exact proportions")
    measurement = AvatarMeasurement(
        id=uuid4(),
        avatar_profile_id=profile.id,
        code="height",
        value=Decimal("178"),
        unit="cm",
        source="user",
        confidence=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[result_with(profile), result_with_many([measurement])])

    loaded = await avatar._load_profile(session, user_id)
    response = await avatar._profile_read(session, loaded)

    assert response.description == "Exact proportions"
    assert response.measurements[0].code == "height"
    assert response.measurements[0].value == Decimal("178")

    missing_session = MagicMock()
    missing_session.execute = AsyncMock(return_value=result_with(None))
    with pytest.raises(HTTPException) as exc_info:
        await avatar._load_profile(missing_session, user_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_profile_returns_null_without_console_noise_for_new_user() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_with(None))

    response = await avatar.get_avatar_profile(user_id=uuid4(), session=session)

    assert response is None


@pytest.mark.asyncio
async def test_update_requires_explicit_consent() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await avatar.update_avatar_profile(
            AvatarProfileUpdate(consent=False),
            user_id=uuid4(),
            session=MagicMock(),
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_generate_without_provider_records_honest_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    profile = profile_for(
        user_id,
        status="ready_for_generation",
        reference_image_id=uuid4(),
        consented_at=datetime.now(UTC),
    )
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            result_with(profile),
            result_with_many([]),
        ]
    )
    session.commit = AsyncMock()
    monkeypatch.setattr(
        avatar,
        "get_settings",
        lambda: Settings(subscriptions_enabled=False, openrouter_api_key=""),
    )

    response = await avatar.generate_avatar(user_id=user_id, session=session)

    assert response.status == ProcessingStatus.FAILED.value
    assert response.generation_error == "provider_not_configured"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_avatar_job_is_committed_before_celery_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    profile = profile_for(
        user_id,
        status="ready_for_generation",
        reference_image_id=uuid4(),
        consented_at=datetime.now(UTC),
    )
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[result_with(profile), result_with_many([])])
    session.commit = AsyncMock()
    monkeypatch.setattr(
        avatar,
        "get_settings",
        lambda: Settings(subscriptions_enabled=False, openrouter_api_key="configured"),
    )
    monkeypatch.setattr(avatar, "reserve_billable_request", AsyncMock(return_value=MagicMock()))

    def enqueue_after_commit(_: str) -> MagicMock:
        assert session.commit.await_count == 1
        return MagicMock(id="avatar-task")

    monkeypatch.setattr(
        "aiwardrobe_worker.tasks.generate_avatar_image.delay",
        enqueue_after_commit,
    )

    response = await avatar.generate_avatar(user_id=user_id, session=session)

    assert response.status == ProcessingStatus.QUEUED.value
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_profile_removes_biometric_links() -> None:
    user_id = uuid4()
    generated_image_id = uuid4()
    profile = profile_for(
        user_id,
        reference_image_id=uuid4(),
        generated_image_id=generated_image_id,
        consented_at=datetime.now(UTC),
        consent_version="2026-07",
        description="Sensitive body description",
    )
    generated_image = MagicMock(id=generated_image_id, user_id=user_id, storage_key="users/test/avatar.png")
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            result_with(profile),
            result_with_many([]),
            result_with_many([generated_image]),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]
    )
    session.commit = AsyncMock()
    storage_delete = AsyncMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("aiwardrobe_api.routers.avatar.ObjectStorage.delete_object", storage_delete)

    try:
        response = await avatar.revoke_avatar_profile(user_id=user_id, session=session)
    finally:
        monkeypatch.undo()

    assert response.status_code == 204
    assert profile.status == "revoked"
    assert profile.description is None
    assert profile.reference_image_id is None
    assert profile.generated_image_id is None
    assert profile.consented_at is None
    assert profile.consent_version is None
    assert profile.revoked_at is not None
    storage_delete.assert_awaited_once_with("users/test/avatar.png")
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_try_on_without_provider_creates_failed_auditable_job(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    item_id = uuid4()
    profile = profile_for(
        user_id,
        status=ProcessingStatus.COMPLETED.value,
        generated_image_id=uuid4(),
    )
    garment = GarmentItem(id=item_id, user_id=user_id, title="Overshirt", category="top")
    try_on_item = TryOnItem(try_on_job_id=uuid4(), item_id=item_id, sort_order=0)
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            result_with(profile),
            result_with_many([garment]),
            result_with_many([try_on_item]),
        ]
    )
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    def add_with_generated_fields(value: object) -> None:
        if value.__class__.__name__ == "TryOnJob":
            value.id = uuid4()  # type: ignore[attr-defined]
            value.created_at = datetime.now(UTC)  # type: ignore[attr-defined]

    session.add.side_effect = add_with_generated_fields
    monkeypatch.setattr(
        avatar,
        "get_settings",
        lambda: Settings(subscriptions_enabled=False, openrouter_api_key=""),
    )

    response = await avatar.create_try_on(
        TryOnCreate(garment_item_ids=[item_id]),
        user_id=user_id,
        session=session,
    )

    assert response.status == ProcessingStatus.FAILED.value
    assert response.error_code == "provider_not_configured"
    assert response.garment_item_ids == [item_id]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_try_on_job_is_committed_before_celery_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    item_id = uuid4()
    profile = profile_for(
        user_id,
        status=ProcessingStatus.COMPLETED.value,
        generated_image_id=uuid4(),
    )
    garment = GarmentItem(id=item_id, user_id=user_id, title="Overshirt", category="top")
    try_on_item = TryOnItem(try_on_job_id=uuid4(), item_id=item_id, sort_order=0)
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            result_with(profile),
            result_with_many([garment]),
            result_with_many([try_on_item]),
        ]
    )
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    def add_with_generated_fields(value: object) -> None:
        if value.__class__.__name__ == "TryOnJob":
            value.id = uuid4()  # type: ignore[attr-defined]
            value.created_at = datetime.now(UTC)  # type: ignore[attr-defined]

    session.add.side_effect = add_with_generated_fields
    monkeypatch.setattr(
        avatar,
        "get_settings",
        lambda: Settings(subscriptions_enabled=False, openrouter_api_key="configured"),
    )
    monkeypatch.setattr(avatar, "reserve_billable_request", AsyncMock(return_value=MagicMock()))

    def enqueue_after_commit(_: str) -> MagicMock:
        assert session.commit.await_count == 1
        return MagicMock(id="try-on-task")

    monkeypatch.setattr(
        "aiwardrobe_worker.tasks.generate_virtual_try_on.delay",
        enqueue_after_commit,
    )

    response = await avatar.create_try_on(
        TryOnCreate(garment_item_ids=[item_id]),
        user_id=user_id,
        session=session,
    )

    assert response.status == ProcessingStatus.QUEUED.value
    queued_job = next(
        call.args[0] for call in session.add.call_args_list if call.args[0].__class__.__name__ == "TryOnJob"
    )
    assert queued_job.provider_job_id == "try-on-task"
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_try_on_rejects_missing_garment(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    profile = profile_for(
        user_id,
        status=ProcessingStatus.COMPLETED.value,
        generated_image_id=uuid4(),
    )
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[result_with(profile), result_with_many([])])
    monkeypatch.setattr(
        avatar,
        "get_settings",
        lambda: Settings(subscriptions_enabled=False, openrouter_api_key=""),
    )

    with pytest.raises(HTTPException) as exc_info:
        await avatar.create_try_on(
            TryOnCreate(garment_item_ids=[uuid4()]),
            user_id=user_id,
            session=session,
        )
    assert exc_info.value.status_code == 404
