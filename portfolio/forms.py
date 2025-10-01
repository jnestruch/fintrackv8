from django import forms
from django.db import transaction
from django.urls import reverse_lazy
from .models import (
    Account, Asset, AssetCategory, Transaction,
    CashDetails, InvestmentDetails,
    RealEstateDetails, PreciousMetalDetails, CollectibleDetails, OtherDetails
)

# Category picker for the first step
class CategorySelectForm(forms.Form):
    category = forms.ChoiceField(choices=AssetCategory.choices, label="Asset category")

class AssetBaseForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["account", "name", "category", "currency"]

    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop("owner", None)
        self.kind = kwargs.pop("kind", None)
        super().__init__(*args, **kwargs)
        if self.owner:
            self.fields["account"].queryset = Account.objects.filter(owner=self.owner, is_active=True)

# --- Investment (Listing OR Token) ---
class InvestmentDetailsForm(forms.ModelForm):
    mode = forms.ChoiceField(
        choices=[("equity","Equity/ETF"),("crypto","Crypto")],
        widget=forms.RadioSelect, 
        required=True, 
        label="Market asset type"
    )
    class Meta:
        model = InvestmentDetails
        fields = ["listing","token","memo"]
        widgets = {
            "listing": forms.Select(attrs={
                "class":"select2-ajax inv-eq",
                "data-url": reverse_lazy("catalog:autocomplete_listings"),
                "data-placeholder": "Search ticker, name, MIC…"
            }),
            "token": forms.Select(attrs={
                "class":"select2-ajax inv-crypto",
                "data-url": reverse_lazy("catalog:autocomplete_tokens"),
                "data-placeholder": "Search symbol, network, contract…"
            }),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["mode"].initial = "equity" if self.instance.listing_id else "crypto"

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        listing = cleaned.get("listing")
        token = cleaned.get("token")

        if mode == "equity":
            if not listing or token: 
                raise forms.ValidationError("Pick a listing (and leave token empty).")
            cleaned["instrument"] = listing.instrument; cleaned["token"] = None
        elif mode == "crypto":
            if not token or listing: 
                raise forms.ValidationError("Pick a token (and leave listing empty).")
            cleaned["instrument"] = token.instrument; cleaned["listing"] = None
        else:
            raise forms.ValidationError("Choose Equity/ETF or Crypto.")
        
        return cleaned

class CashDetailsForm(forms.ModelForm):
    class Meta: model = CashDetails; fields = ["account_ref"]

class RealEstateDetailsForm(forms.ModelForm):
    class Meta: model = RealEstateDetails; fields = ["address","country","cadastral_id","area_sqm"]

class PreciousMetalDetailsForm(forms.ModelForm):
    class Meta: model = PreciousMetalDetails; fields = ["metal","purity","form","weight_grams"]

class CollectibleDetailsForm(forms.ModelForm):
    class Meta: model = CollectibleDetails; fields = ["category","year","certificate_id","notes"]

class OtherDetailsForm(forms.ModelForm):
    class Meta: model = OtherDetails; fields = ["description"]

DETAIL_FORM_BY_KIND = {
    AssetCategory.CASH: CashDetailsForm,
    AssetCategory.INVESTMENT: InvestmentDetailsForm,
    AssetCategory.REAL_ESTATE: RealEstateDetailsForm,
    AssetCategory.PRECIOUS_METAL: PreciousMetalDetailsForm,
    AssetCategory.COLLECTIBLE: CollectibleDetailsForm,
    AssetCategory.OTHER: OtherDetailsForm,
}

def _related_name_for_kind(kind: str) -> str:
    return {
        AssetCategory.CASH: "cash", AssetCategory.INVESTMENT: "investment", AssetCategory.REAL_ESTATE: "realestate",
        AssetCategory.PRECIOUS_METAL: "metal", AssetCategory.COLLECTIBLE: "collectible", AssetCategory.OTHER: "other",
    }[kind]

def save_asset_with_details(*, owner, kind, asset_form: AssetBaseForm, detail_form: forms.ModelForm, instance=None):
    with transaction.atomic():
        asset = instance or Asset(kind=kind)
        asset_form.instance = asset
        asset = asset_form.save()
        detail = getattr(asset, _related_name_for_kind(kind), None)
        detail_form.instance = detail or detail_form._meta.model(asset=asset)
        detail_form.save()
        return asset

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["timestamp", "txn_type", "quantity", "amount", "fee", "memo"]
        widgets = {"timestamp": forms.DateTimeInput(attrs={"type": "datetime-local"})}
