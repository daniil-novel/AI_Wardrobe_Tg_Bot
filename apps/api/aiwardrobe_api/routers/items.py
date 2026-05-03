from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter

from aiwardrobe_core.enums import AvailabilityStatus, GarmentStatus
from aiwardrobe_core.schemas import GarmentItemRead, GarmentItemUpdate

router = APIRouter(prefix="/items", tags=["garment-items"])


def sample_item(item_id: UUID | None = None) -> GarmentItemRead:
    return GarmentItemRead(
        id=item_id or uuid4(),
        title="Джинсовая куртка",
        category="outerwear",
        season=["spring", "autumn", "demi"],
        main_color="dark blue",
        confidence=Decimal("0.87"),
        status=GarmentStatus.NEEDS_CONFIRMATION.value,
        availability_status=AvailabilityStatus.AVAILABLE.value,
        designer_attributes={
            "palette_role": "base",
            "silhouette": "relaxed",
            "designer_reasoning": "Структурный верхний слой для casual и smart casual образов.",
        },
    )


@router.get("", response_model=list[GarmentItemRead])
async def list_items() -> list[GarmentItemRead]:
    return [sample_item()]


@router.get("/{item_id}", response_model=GarmentItemRead)
async def get_item(item_id: UUID) -> GarmentItemRead:
    return sample_item(item_id)


@router.patch("/{item_id}", response_model=GarmentItemRead)
async def update_item(item_id: UUID, payload: GarmentItemUpdate) -> GarmentItemRead:
    item = sample_item(item_id)
    data = item.model_dump()
    for key, value in payload.model_dump(exclude_none=True).items():
        data[key] = value
    return GarmentItemRead.model_validate(data)


@router.post("/{item_id}/confirm", response_model=GarmentItemRead)
async def confirm_item(item_id: UUID) -> GarmentItemRead:
    item = sample_item(item_id)
    return item.model_copy(update={"status": GarmentStatus.CONFIRMED.value})


@router.post("/{item_id}/hide", response_model=GarmentItemRead)
async def hide_item(item_id: UUID) -> GarmentItemRead:
    item = sample_item(item_id)
    return item.model_copy(update={"status": GarmentStatus.HIDDEN.value})


@router.post("/{item_id}/wear", response_model=GarmentItemRead)
async def wear_item(item_id: UUID) -> GarmentItemRead:
    return sample_item(item_id)


@router.post("/{item_id}/research")
async def rerun_research(item_id: UUID) -> dict[str, UUID | str]:
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/generate-product-image")
async def generate_product_image(item_id: UUID) -> dict[str, UUID | str]:
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/find-product-photo")
async def find_product_photo(item_id: UUID) -> dict[str, UUID | str]:
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/find-similar")
async def find_similar(item_id: UUID) -> dict[str, UUID | str]:
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/delete-original")
async def delete_original(item_id: UUID) -> dict[str, UUID | str]:
    return {"id": item_id, "status": "original_deleted"}


@router.delete("/{item_id}")
async def delete_item(item_id: UUID) -> dict[str, UUID | str]:
    return {"id": item_id, "status": "deleted"}
