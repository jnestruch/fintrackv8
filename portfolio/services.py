from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from django.utils import timezone

from catalog.models import Instrument, InstrumentKind, Quote
from portfolio.models import Asset, AssetCategory, PreciousMetalDetails

OZT_TO_GRAM = Decimal("31.1034768")


def _latest_quote_for_listing(listing_id) -> Optional[Quote]:
    if not listing_id:
        return None
    return Quote.objects.filter(listing_id=listing_id).order_by("-ts").first()


def _latest_quote_for_token(token_id) -> Optional[Quote]:
    if not token_id:
        return None
    return Quote.objects.filter(token_id=token_id).order_by("-ts").first()


def _latest_quote_for_instrument(instrument_id) -> Optional[Quote]:
    if not instrument_id:
        return None
    return Quote.objects.filter(instrument_id=instrument_id).order_by("-ts").first()


def _commodity_instrument_by_name(name: str) -> Optional[Instrument]:
    return Instrument.objects.filter(kind=InstrumentKind.COMMODITY, name=name).first()


def value_precious_metal(detail: PreciousMetalDetails) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Returns (market_value, currency) for a PreciousMetalDetails row.
    Uses the latest instrument-level quote for the metal (e.g., Gold per troy ounce).
    """
    metal_name_map = {
        "GOLD": "Gold",
        "SILVER": "Silver",
        "PLATINUM": "Platinum",
        "PALLADIUM": "Palladium",
    }
    name = metal_name_map.get(detail.metal)
    if not name:
        return (None, None)

    inst = _commodity_instrument_by_name(name)
    if not inst:
        return (None, None)

    q = _latest_quote_for_instrument(inst.id)
    if not q:
        return (None, None)

    # Assume commodity quote is per troy ounce in q.currency
    price_per_gram = (Decimal(q.price) / OZT_TO_GRAM).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    fine_weight = (detail.weight_grams * detail.purity).quantize(Decimal("0.000"), rounding=ROUND_HALF_UP)
    value = (fine_weight * price_per_gram).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (value, q.currency)


def market_value_for_asset(asset: Asset) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Returns (market_value, currency) for any asset, or (None, None) if not priced.
    """
    if asset.category == AssetCategory.INVESTMENT and hasattr(asset, "investment"):
        inv = asset.investment
        if inv.listing_id:
            q = _latest_quote_for_listing(inv.listing_id)
            if q:
                return (Decimal(q.price), q.currency)
        if inv.token_id:
            q = _latest_quote_for_token(inv.token_id)
            if q:
                return (Decimal(q.price), q.currency)
        # fallback (rare): instrument-level quote
        q = _latest_quote_for_instrument(inv.instrument_id)
        if q:
            return (Decimal(q.price), q.currency)
        return (None, None)

    if asset.category == AssetCategory.PRECIOUS_METAL and hasattr(asset, "metal"):
        return value_precious_metal(asset.metal)

    # For other categories (cash/real estate/collectible/other), no pricing by default
    return (None, None)

