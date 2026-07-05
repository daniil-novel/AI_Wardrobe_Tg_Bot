from uuid import UUID

from aiwardrobe_core.models import GarmentItem, StyleDna, UserStyleRule, WardrobeHealthSnapshot
from aiwardrobe_core.schemas import StyleDnaRead, StyleRuleCreate, StyleRuleRead, WardrobeHealthRead
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(tags=["style"])


def style_dna_read_model(style_dna: StyleDna) -> StyleDnaRead:
    return StyleDnaRead(
        dominant_styles=list(style_dna.dominant_styles),
        avoided_styles=list(style_dna.avoided_styles),
        preferred_color_families=list(style_dna.preferred_color_families),
        avoided_color_families=list(style_dna.avoided_color_families),
        preferred_silhouettes=list(style_dna.preferred_silhouettes),
        preferred_formality_range=dict(style_dna.preferred_formality_range),
        confidence=style_dna.confidence,
    )


def rule_read_model(rule: UserStyleRule) -> StyleRuleRead:
    return StyleRuleRead(
        id=rule.id,
        natural_language_rule=rule.natural_language_rule,
        parsed_rule=dict(rule.parsed_rule),
        enabled=rule.enabled,
    )


@router.get("/style-dna", response_model=StyleDnaRead)
async def get_style_dna(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> StyleDnaRead:
    style_dna = await load_or_create_style_dna(session, user_id)
    return style_dna_read_model(style_dna)


@router.patch("/style-dna", response_model=StyleDnaRead)
async def patch_style_dna(
    payload: StyleDnaRead, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> StyleDnaRead:
    style_dna = await load_or_create_style_dna(session, user_id)
    data = payload.model_dump()
    for key, value in data.items():
        setattr(style_dna, key, value)
    await session.commit()
    await session.refresh(style_dna)
    return style_dna_read_model(style_dna)


@router.post("/style-dna/calibrate")
async def calibrate_style_dna(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> dict[str, str]:
    await load_or_create_style_dna(session, user_id)
    return {"status": "queued"}


@router.get("/wardrobe/health", response_model=WardrobeHealthRead)
async def wardrobe_health(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> WardrobeHealthRead:
    result = await session.execute(
        select(WardrobeHealthSnapshot)
        .where(WardrobeHealthSnapshot.user_id == user_id)
        .order_by(WardrobeHealthSnapshot.created_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        return await calculate_wardrobe_health(session, user_id)
    return WardrobeHealthRead(
        score=snapshot.score,
        coverage_by_season=dict(snapshot.coverage_by_season),
        coverage_by_event=dict(snapshot.coverage_by_event),
        missing_roles=list(snapshot.missing_roles),
        duplicate_groups=list(snapshot.duplicate_groups),
        orphan_items=list(snapshot.orphan_items),
    )


async def calculate_wardrobe_health(session: AsyncSession, user_id: UUID) -> WardrobeHealthRead:
    result = await session.execute(
        select(GarmentItem).where(
            GarmentItem.user_id == user_id,
            GarmentItem.deleted_at.is_(None),
            GarmentItem.is_hidden.is_(False),
        )
    )
    items = list(result.scalars())
    if not items:
        return WardrobeHealthRead(
            score=0,
            missing_roles=[
                "Добавьте верх, низ, обувь и верхний слой, чтобы начать считать покрытие гардероба.",
            ],
            coverage_by_season={},
            coverage_by_event={},
        )

    required_categories = {
        "top": "верх",
        "bottom": "низ",
        "shoes": "обувь",
        "outerwear": "верхний слой",
    }
    category_counts = {category: 0 for category in required_categories}
    season_counts = {"winter": 0, "spring": 0, "summer": 0, "autumn": 0, "all_season": 0}
    duplicates: dict[str, int] = {}
    orphan_items: list[str] = []
    for item in items:
        if item.category in category_counts:
            category_counts[item.category] += 1
        for season in item.season:
            if isinstance(season, str) and season in season_counts:
                season_counts[season] += 1
        key = f"{item.category}:{(item.main_color or '').lower()}:{(item.title or '').lower()[:30]}"
        duplicates[key] = duplicates.get(key, 0) + 1
        if item.confidence < 0.55:
            orphan_items.append(f"{item.title}: низкая уверенность распознавания")

    missing_roles = [
        f"Не хватает: {label}." for category, label in required_categories.items() if category_counts[category] == 0
    ]
    if season_counts["winter"] == 0 and season_counts["all_season"] == 0:
        missing_roles.append("Нет вещей для холодной погоды.")
    if category_counts["shoes"] < 2:
        missing_roles.append("Мало обуви для разных погодных сценариев.")

    duplicate_groups = [key for key, count in duplicates.items() if count > 1]
    category_score = sum(1 for count in category_counts.values() if count > 0) / len(required_categories)
    season_score = min(1.0, (sum(1 for count in season_counts.values() if count > 0) / 5) + 0.15)
    confidence_score = sum(float(item.confidence) for item in items) / max(len(items), 1)
    score = round(max(0, min(100, category_score * 45 + season_score * 30 + confidence_score * 25)))

    return WardrobeHealthRead(
        score=score,
        coverage_by_season=season_counts,
        coverage_by_event={
            "base_roles": category_counts,
            "item_count": len(items),
        },
        missing_roles=missing_roles,
        duplicate_groups=duplicate_groups,
        orphan_items=orphan_items,
    )


@router.post("/rules", response_model=StyleRuleRead)
async def create_rule(
    payload: StyleRuleCreate, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> StyleRuleRead:
    rule = UserStyleRule(user_id=user_id, natural_language_rule=payload.natural_language_rule, parsed_rule={})
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule_read_model(rule)


@router.get("/rules", response_model=list[StyleRuleRead])
async def list_rules(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> list[StyleRuleRead]:
    result = await session.execute(
        select(UserStyleRule).where(UserStyleRule.user_id == user_id).order_by(UserStyleRule.created_at.desc())
    )
    return [rule_read_model(rule) for rule in result.scalars()]


@router.patch("/rules/{rule_id}", response_model=StyleRuleRead)
async def patch_rule(
    rule_id: UUID, payload: StyleRuleCreate, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> StyleRuleRead:
    result = await session.execute(
        select(UserStyleRule).where(UserStyleRule.id == rule_id, UserStyleRule.user_id == user_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style rule not found.")
    rule.natural_language_rule = payload.natural_language_rule
    await session.commit()
    await session.refresh(rule)
    return rule_read_model(rule)


async def load_or_create_style_dna(session: AsyncSession, user_id: UUID) -> StyleDna:
    result = await session.execute(select(StyleDna).where(StyleDna.user_id == user_id))
    style_dna = result.scalar_one_or_none()
    if style_dna is None:
        style_dna = StyleDna(user_id=user_id)
        session.add(style_dna)
        await session.flush()
    return style_dna
