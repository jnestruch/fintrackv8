from __future__ import annotations

import sys
from decimal import Decimal
from typing import Optional, Dict

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from portfolio.models import (
    Asset, AssetCategory, Account,
    AssetType,
    InvestmentDetails, CashDetails, RealEstateDetails,
    PreciousMetalDetails, CollectibleDetails, OtherDetails,
    Transaction,
)
from catalog.models import Instrument, Listing, Token


# --------------------------
# Catalog helpers
# --------------------------
def get_listing(ticker: str, mic: Optional[str] = None) -> Optional[Listing]:
    qs = Listing.objects.filter(ticker=ticker)
    if mic:
        qs = qs.filter(exchange__mic=mic)
    return qs.select_related("instrument", "exchange").first()

def get_token(symbol: str, network_code: Optional[str] = None) -> Optional[Token]:
    qs = Token.objects.filter(symbol=symbol)
    if network_code:
        qs = qs.filter(network__code=network_code)
    return qs.select_related("instrument", "network").first()


# --------------------------
# Taxonomy helper (now slug/level-aware)
# --------------------------
def ensure_type_path(path: str) -> AssetType:
    """
    Ensure an AssetType exists for a 'A > B > C' path.
    Fills slug and level if those fields exist on the model.
    Returns the deepest node.
    """
    # Detect optional fields on your model
    has_slug = any(f.name == "slug" for f in AssetType._meta.get_fields() if hasattr(f, "name"))
    has_level = any(f.name == "level" for f in AssetType._meta.get_fields() if hasattr(f, "name"))

    node: Optional[AssetType] = None
    level = 0 if has_level else None

    for name in [p.strip() for p in path.split(">") if p.strip()]:
        level = (level + 1) if has_level else None
        defaults = {}
        qu = AssetType.objects  # base manager

        if has_slug:
            s = slugify(name) or name.lower().replace(" ", "-")
            defaults["slug"] = s

        if has_level:
            defaults["level"] = level

        # Decide the lookup: prefer unique slug if present; otherwise (name, parent)
        if has_slug:
            obj, created = qu.get_or_create(slug=defaults["slug"], defaults={"name": name, "parent": node, **defaults})
        else:
            obj, created = qu.get_or_create(name=name, parent=node, defaults=defaults)

        # If it existed but fields differ (name, parent, level), update minimally
        changed = False
        if obj.name != name:
            obj.name = name; changed = True
        if obj.parent_id != (node.id if node else None):
            obj.parent = node; changed = True
        if has_level and getattr(obj, "level", level) != level:
            obj.level = level; changed = True
        if has_slug and getattr(obj, "slug", defaults["slug"]) != defaults["slug"]:
            obj.slug = defaults["slug"]; changed = True
        if changed:
            obj.save()

        node = obj

    assert node is not None
    return node


# --------------------------
# Demo accounts
# --------------------------
def seed_demo_accounts(user) -> Dict[str, Account]:
    accounts: Dict[str, Account] = {}
    for name in ["Brokerage", "Bank", "Crypto Wallet"]:
        acc, _ = Account.objects.get_or_create(owner=user, name=name)
        accounts[name] = acc
    return accounts


def add_txn(asset: Asset, amount: Decimal, memo: str):
    Transaction.objects.get_or_create(
        asset=asset,
        timestamp=timezone.now(),
        amount=amount,
        memo=memo,
    )


@transaction.atomic
def seed_demo_assets(user, accounts: Dict[str, Account]):
    created = []

    # ---------- Investment: Apple (AAPL @ XNAS) ----------
    aapl_listing = get_listing("AAPL", mic="XNAS")
    if aapl_listing:
        asset, _ = Asset.objects.get_or_create(
            account=accounts["Brokerage"],
            name="Apple Inc. Position",
            category=AssetCategory.INVESTMENT,
            type=ensure_type_path("Investment > Stock > US Stocks"),
            defaults={"currency": "USD"},
        )
        inv, _ = InvestmentDetails.objects.get_or_create(
            asset=asset,
            defaults={"listing": aapl_listing, "token": None, "memo": "Long-term core holding"},
        )
        inv.save()
        add_txn(asset, Decimal("10000.00"), "Initial buy (aggregate)")
        created.append(asset)
    else:
        print("WARN: Listing AAPL@XNAS not found; skipping Apple demo asset.", file=sys.stderr)

    # ---------- Investment: IVV ETF (IVV @ XNYS) ----------
    ivv_listing = get_listing("IVV", mic="XNYS")
    if ivv_listing:
        asset, _ = Asset.objects.get_or_create(
            account=accounts["Brokerage"],
            name="S&P 500 ETF",
            category=AssetCategory.INVESTMENT,
            type=ensure_type_path("Investment > ETF > Broad Market"),
            defaults={"currency": "USD"},
        )
        inv, _ = InvestmentDetails.objects.get_or_create(
            asset=asset,
            defaults={"listing": ivv_listing, "token": None, "memo": "Index ETF"},
        )
        inv.save()
        add_txn(asset, Decimal("5000.00"), "Initial buy")
        created.append(asset)
    else:
        print("WARN: Listing IVV@XNYS not found; skipping IVV demo asset.", file=sys.stderr)

    # ---------- Investment: Ethereum (ETH on ETH) ----------
    eth_token = get_token("ETH", network_code="ETH")
    if eth_token:
        asset, _ = Asset.objects.get_or_create(
            account=accounts["Crypto Wallet"],
            name="Ethereum",
            category=AssetCategory.INVESTMENT,
            type=ensure_type_path("Investment > Crypto > Layer1"),
            defaults={"currency": "USD"},
        )
        inv, _ = InvestmentDetails.objects.get_or_create(
            asset=asset,
            defaults={"token": eth_token, "listing": None, "memo": "On-chain holdings"},
        )
        inv.save()
        add_txn(asset, Decimal("2500.00"), "On-chain buy")
        created.append(asset)
    else:
        print("WARN: Token ETH@ETH not found; skipping ETH demo asset.", file=sys.stderr)

    # ---------- Investment: USDC (ETH) ----------
    usdc_token = get_token("USDC", network_code="ETH")
    if usdc_token:
        asset, _ = Asset.objects.get_or_create(
            account=accounts["Crypto Wallet"],
            name="USDC (Ethereum)",
            category=AssetCategory.INVESTMENT,
            type=ensure_type_path("Investment > Crypto > Stablecoin"),
            defaults={"currency": "USD"},
        )
        inv, _ = InvestmentDetails.objects.get_or_create(
            asset=asset,
            defaults={"token": usdc_token, "listing": None, "memo": "Stable holdings"},
        )
        inv.save()
        add_txn(asset, Decimal("1500.00"), "Deposit")
        created.append(asset)
    else:
        print("WARN: Token USDC@ETH not found; skipping USDC demo asset.", file=sys.stderr)

    # ---------- Cash ----------
    cash_asset, _ = Asset.objects.get_or_create(
        account=accounts["Bank"],
        name="Main Checking",
        category=AssetCategory.CASH,
        type=ensure_type_path("Cash"),
        defaults={"currency": "USD"},
    )
    CashDetails.objects.get_or_create(asset=cash_asset, defaults={"account_ref": "CHK-001"})
    add_txn(cash_asset, Decimal("3000.00"), "Opening balance")
    created.append(cash_asset)

    # ---------- Real estate ----------
    re_asset, _ = Asset.objects.get_or_create(
        account=accounts["Brokerage"],
        name="Apartment Barcelona",
        category=AssetCategory.REAL_ESTATE,
        type=ensure_type_path("Real estate > Residential"),
        defaults={"currency": "EUR"},
    )
    RealEstateDetails.objects.get_or_create(
        asset=re_asset,
        defaults={
            "address": "Carrer de l'Exemple 123, Barcelona",
            "country": "ES",
            "cadastral_id": "ES-ABC-2025",
            "area_sqm": Decimal("75.0"),
        },
    )
    add_txn(re_asset, Decimal("250000.00"), "Acquisition (notional)")
    created.append(re_asset)

    # ---------- Precious metal ----------
    pm_asset, _ = Asset.objects.get_or_create(
        account=accounts["Brokerage"],
        name="Gold Bars",
        category=AssetCategory.PRECIOUS_METAL,
        type=ensure_type_path("Precious metals > Gold"),
        defaults={"currency": "USD"},
    )
    PreciousMetalDetails.objects.get_or_create(
        asset=pm_asset,
        defaults={
            "metal": PreciousMetalDetails.Metal.GOLD,
            "purity": Decimal("0.999"),
            "form": "Bar",
            "weight_grams": Decimal("100.0"),
        },
    )
    add_txn(pm_asset, Decimal("6500.00"), "Purchase")
    created.append(pm_asset)

    # ---------- Collectible ----------
    coll_asset, _ = Asset.objects.get_or_create(
        account=accounts["Brokerage"],
        name="Art Print",
        category=AssetCategory.COLLECTIBLE,
        type=ensure_type_path("Collectibles > Art"),
        defaults={"currency": "USD"},
    )
    CollectibleDetails.objects.get_or_create(
        asset=coll_asset,
        defaults={
            "category": "Art Print",
            "year": 2020,
            "certificate_id": "ART-XYZ-2020",
            "notes": "Limited edition 12/100",
        },
    )
    add_txn(coll_asset, Decimal("1200.00"), "Purchase")
    created.append(coll_asset)

    # ---------- Other ----------
    other_asset, _ = Asset.objects.get_or_create(
        account=accounts["Brokerage"],
        name="Miscellaneous",
        category=AssetCategory.OTHER,
        type=ensure_type_path("Other"),
        defaults={"currency": "USD"},
    )
    OtherDetails.objects.get_or_create(asset=other_asset, defaults={"description": "Misc asset placeholder"})
    created.append(other_asset)

    return created


class Command(BaseCommand):
    help = "Seed Portfolio data: ensures taxonomy (slug/level aware), demo accounts, assets & transactions (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Existing username to attach demo data to.")
        parser.add_argument("--email", help="Existing user email to attach demo data to (if username not provided).")
        parser.add_argument("--create-user", action="store_true", help="Create a demo user if not found (username 'demo').")
        parser.add_argument("--demo-password", default="demo1234", help="Password for created demo user.")
        parser.add_argument("--taxonomy-only", action="store_true", help="Ensure taxonomy root nodes only; skip assets/accounts.")

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()

        # Only taxonomy? Ensure roots and exit
        if opts.get("taxonomy_only"):
            for root in ["Cash", "Investment", "Real estate", "Precious metals", "Collectibles", "Other"]:
                ensure_type_path(root)
            self.stdout.write(self.style.SUCCESS("Ensured taxonomy root nodes."))
            return

        # Resolve or create a user
        user = None
        if opts.get("username"):
            user = User.objects.filter(username=opts["username"]).first()
            if not user:
                raise CommandError(f"User with username '{opts['username']}' not found.")
        elif opts.get("email"):
            user = User.objects.filter(email=opts["email"]).first()
            if not user:
                raise CommandError(f"User with email '{opts['email']}' not found.")
        else:
            user = User.objects.order_by("id").first()

        if not user and opts.get("create_user"):
            user = User.objects.create_user(username="demo", email="demo@example.com", password=opts.get("demo_password") or "demo1234")
            self.stdout.write(self.style.SUCCESS("Created demo user 'demo' (password from --demo-password)."))

        if not user:
            raise CommandError("No target user found. Pass --username or --email, or use --create-user.")

        # Seed demo accounts & assets
        accounts = seed_demo_accounts(user)
        assets = seed_demo_assets(user, accounts)

        self.stdout.write(self.style.SUCCESS(f"Demo accounts ensured: {len(accounts)}"))
        self.stdout.write(self.style.SUCCESS(f"Demo assets ensured: {len(assets)}"))
        self.stdout.write(self.style.SUCCESS("Portfolio seeding complete."))
