from django.conf import settings
from django.db import models
from django.db.models import Q, F, CheckConstraint, UniqueConstraint
from catalog.models import Instrument, Listing, Token
from django.core.exceptions import ValidationError

class AccountType(models.TextChoices):
    BROKERAGE = "BROKERAGE", "Brokerage"
    BANK      = "BANK", "Bank"
    WALLET    = "WALLET", "Crypto wallet"
    CASH      = "CASH", "Cash"
    PROPERTY  = "PROPERTY", "Property"
    OTHER     = "OTHER", "Other"

# User account model (e.g. brokerage, bank, wallet, property)
class Account(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.OTHER)
    base_currency = models.CharField(max_length=3, default="EUR")
    institution = models.CharField(max_length=120, blank=True)
    account_ref = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("owner", "name")]
        indexes = [models.Index(fields=["owner", "is_active"])]
    
    def __str__(self): return f"{self.name} ({self.owner})"

#Hierarchical asset types (e.g. Equity -> Stock, ETF; Crypto -> Coin, Token)
class AssetType(models.Model):
    """
    Adjacency-list category tree: level 1..3 (or more if you ever need).
    Examples:
      L1: Investment
      L2: Stock
      L3: US Stocks (optional)
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.PROTECT)
    level = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = [("parent", "name")]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["level"])]
        verbose_name = "Asset type"
        verbose_name_plural = "Asset types"
    
    def __str__(self): return self.name

    @property
    def full_path(self):
        """Return the full hierarchy as a string, e.g. 'Investment > Stock > US Stock'."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

# Asset categories (broad classification)
class AssetCategory(models.TextChoices):
    CASH = "CASH", "Cash"
    INVESTMENT = "INVESTMENT", "Investment"  # covers stocks, ETFs, crypto, bonds, etc.
    REAL_ESTATE = "REAL_ESTATE", "Real estate"
    PRECIOUS_METAL = "PRECIOUS_METAL", "Precious metal"
    COLLECTIBLE = "COLLECTIBLE", "Collectible"
    OTHER = "OTHER", "Other"

# Main Asset model
class Asset(models.Model):
    """
    User-owned asset. Fine-grained specifics live in per-category detail tables:
      - InvestmentDetails (instrument + one of: listing OR token)
      - CashDetails
      - RealEstateDetails
      - PreciousMetalDetails
      - CollectibleDetails
      - OtherDetails
    """
    account = models.ForeignKey("portfolio.Account", on_delete=models.CASCADE, related_name="assets")
    name = models.CharField(max_length=200)

    # Broad bucket; 'INVESTMENT' covers stocks/ETFs/crypto/etc. The concrete thing is in InvestmentDetails. 
    category = models.CharField(max_length=32, choices=AssetCategory.choices)  # << changed
    type = models.ForeignKey("portfolio.AssetType", on_delete=models.PROTECT, related_name="assets")

    # Reporting currency for this asset (can differ from account base currency)
    currency = models.CharField(max_length=3, default="USD")

    # Operational fields
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Extra JSON field for future-proofing / custom data
    # Free-form provider metadata (IDs, external refs, etc.)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "category"]),
            models.Index(fields=["type"]),
            models.Index(fields=["is_active"]),
        ]

        constraints = [
            UniqueConstraint(
                fields=["account"],
                condition=Q(category="CASH"),
                name="unique_one_cash_asset_per_account",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"

    @property
    def detail(self):
        """
        Convenience accessor to the attached detail row for this asset's category.
        Returns the related detail instance or None if missing.
        """
        return (
            getattr(self, "investment", None) or
            getattr(self, "cash", None) or
            getattr(self, "realestate", None) or
            getattr(self, "metal", None) or
            getattr(self, "collectible", None) or
            getattr(self, "other", None)
        )

# Specific details for different asset categories
class InvestmentDetails(models.Model):
    asset = models.OneToOneField("portfolio.Asset", on_delete=models.CASCADE, related_name="investment")

    # Always keep a canonical link to the instrument (equity/etf/crypto/bond…)
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, editable=False, related_name="holdings")

    # Choose ONE of the below (for price/source specificity)
    listing = models.ForeignKey(Listing, null=True, blank=True, on_delete=models.PROTECT, related_name="positions")
    token = models.ForeignKey(Token, null=True, blank=True, on_delete=models.PROTECT, related_name="holdings")

    memo = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            # Exactly one of listing or token must be set (XOR)
            CheckConstraint(
                name="one_listing_or_token",
                check=(
                    (Q(listing__isnull=False) & Q(token__isnull=True)) |
                    (Q(listing__isnull=True) & Q(token__isnull=False))
                ),
            ),
        ]
    
    def clean(self):
        # Enforce XOR in Python too (for clearer error messages in forms/admin).
        has_listing = self.listing_id is not None
        has_token   = self.token_id   is not None
        if has_listing == has_token:
            raise ValidationError("Pick exactly one: a Listing (equity/ETF) OR a Token (crypto).")

        # Auto-set instrument and validate consistency
        derived = self.listing.instrument if has_listing else self.token.instrument
        if self.instrument_id and self.instrument_id != derived.id:
            raise ValidationError("Instrument must match the selected listing/token.")
        self.instrument = derived

    def save(self, *args, **kwargs):
        # Ensure instrument is derived before saving (covers non-form code paths).
        self.full_clean()  # runs clean()
        super().save(*args, **kwargs)
        
# Cash asset Category details
class CashDetails(models.Model):
    asset = models.OneToOneField("portfolio.Asset", on_delete=models.CASCADE, related_name="cash")
    account_ref = models.CharField(max_length=120, blank=True)

# Real estate asset Category details
class RealEstateDetails(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name="realestate")
    address = models.CharField(max_length=250)
    country = models.CharField(max_length=2)
    cadastral_id = models.CharField(max_length=64, blank=True)
    area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

# Precious metal asset Category details
class PreciousMetalDetails(models.Model):
    class Metal(models.TextChoices):
        GOLD="GOLD","Gold"; SILVER="SILVER","Silver"; PLATINUM="PLATINUM","Platinum"; PALLADIUM="PALLADIUM","Palladium"
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name="metal")
    metal = models.CharField(max_length=12, choices=Metal.choices)
    purity = models.DecimalField(max_digits=6, decimal_places=3)
    form = models.CharField(max_length=40, blank=True)
    weight_grams = models.DecimalField(max_digits=12, decimal_places=3)

# Collectible asset Category details
class CollectibleDetails(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name="collectible")
    category = models.CharField(max_length=80)
    year = models.PositiveIntegerField(null=True, blank=True)
    certificate_id = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

# Other asset Category details
class OtherDetails(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name="other")
    description = models.TextField(blank=True)


# Transactions linked to assets
class Transaction(models.Model):
    class TxnType(models.TextChoices):
        BUY="BUY","Buy"; SELL="SELL","Sell"; DEPOSIT="DEPOSIT","Deposit"; WITHDRAWAL="WITHDRAWAL","Withdrawal"
        INCOME="INCOME","Income"; EXPENSE="EXPENSE","Expense"; ADJUSTMENT="ADJUSTMENT","Adjustment"
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="transactions")
    timestamp = models.DateTimeField()
    txn_type = models.CharField(max_length=16, choices=TxnType.choices)
    quantity = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    fee = models.DecimalField(max_digits=24, decimal_places=8, default=0)
    memo = models.CharField(max_length=280, blank=True)

    class Meta: 
        indexes=[models.Index(fields=["asset","timestamp"])]; ordering=["-timestamp"]
    
    def __str__(self): 
        return f"{self.txn_type} {self.amount} {self.asset.currency} on {self.timestamp.date()}"
