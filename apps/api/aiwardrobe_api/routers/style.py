from uuid import UUID

from aiwardrobe_core.models import StyleDna, UserStyleRule, WardrobeHealthSnapshot
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
        return WardrobeHealthRead()
    return WardrobeHealthRead(
        score=snapshot.score,
        coverage_by_season=dict(snapshot.coverage_by_season),
        coverage_by_event=dict(snapshot.coverage_by_event),
        missing_roles=list(snapshot.missing_roles),
        duplicate_groups=list(snapshot.duplicate_groups),
        orphan_items=list(snapshot.orphan_items),
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
