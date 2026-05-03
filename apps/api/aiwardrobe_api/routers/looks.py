from decimal import Decimal
from uuid import UUID, uuid4

from aiwardrobe_core.schemas import LookCardRead
from fastapi import APIRouter

router = APIRouter(prefix="/looks", tags=["looks"])


def sample_look(look_id: UUID | None = None) -> LookCardRead:
    return LookCardRead(
        id=look_id or uuid4(),
        title="Город + метро + офис",
        is_favorite=True,
        style_tags=["casual", "smart casual"],
        designer_reasoning={"summary": "Нейтральная база, слой и удобная обувь."},
        confidence=Decimal("0.92"),
    )


@router.get("", response_model=list[LookCardRead])
async def list_looks() -> list[LookCardRead]:
    return [sample_look()]


@router.get("/{look_id}", response_model=LookCardRead)
async def get_look(look_id: UUID) -> LookCardRead:
    return sample_look(look_id)


@router.post("/{look_id}/favorite", response_model=LookCardRead)
async def favorite_look(look_id: UUID) -> LookCardRead:
    return sample_look(look_id)


@router.delete("/{look_id}/favorite", response_model=LookCardRead)
async def unfavorite_look(look_id: UUID) -> LookCardRead:
    return sample_look(look_id).model_copy(update={"is_favorite": False})


@router.post("/{look_id}/generate-similar")
async def generate_similar(look_id: UUID) -> dict[str, UUID | str]:
    return {"id": look_id, "status": "queued"}


@router.delete("/{look_id}")
async def delete_look(look_id: UUID) -> dict[str, UUID | str]:
    return {"id": look_id, "status": "deleted"}
