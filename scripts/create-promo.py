import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.entitlements import generate_promo_code, hash_promo_code
from aiwardrobe_core.enums import SubscriptionPlan
from aiwardrobe_core.models import PromoCode
from sqlalchemy import select


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a hashed AI Wardrobe promo code.")
    parser.add_argument("--code", help="Optional high-entropy code; generated securely when omitted.")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--max-redemptions", type=int, default=1)
    parser.add_argument("--valid-days", type=int, default=30)
    parser.add_argument("--label", default="One-day full-access test")
    return parser.parse_args()


async def create_promo(args: argparse.Namespace) -> str:
    if args.hours < 1 or args.max_redemptions < 1 or args.valid_days < 1:
        raise ValueError("hours, max-redemptions, and valid-days must be positive.")
    code = args.code or generate_promo_code()
    code_hash = hash_promo_code(code)
    now = datetime.now(UTC)
    async with get_session_factory()() as session:
        existing_result = await session.execute(select(PromoCode).where(PromoCode.code_hash == code_hash))
        if existing_result.scalar_one_or_none() is not None:
            raise ValueError("Promo code already exists.")
        session.add(
            PromoCode(
                code_hash=code_hash,
                label=args.label,
                plan=SubscriptionPlan.PREMIUM.value,
                duration_hours=args.hours,
                max_redemptions=args.max_redemptions,
                redemption_count=0,
                valid_from=now,
                valid_until=now + timedelta(days=args.valid_days),
                enabled=True,
            )
        )
        await session.commit()
    return code


def main() -> None:
    code = asyncio.run(create_promo(parse_args()))
    print(code)


if __name__ == "__main__":
    main()
