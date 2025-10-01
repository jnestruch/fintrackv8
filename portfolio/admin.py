from django.contrib import admin
from .models import (
    Account, AccountType, AssetType, Asset, AssetCategory, Transaction,
    CashDetails, InvestmentDetails,
    RealEstateDetails, PreciousMetalDetails, CollectibleDetails, OtherDetails
)

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "type", "base_currency", "is_active", "created_at")
    list_filter  = ("type", "is_active", "base_currency")
    search_fields = ("name", "owner__username", "institution", "account_ref")
    autocomplete_fields = ("owner",)

@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("name","slug","level","parent")
    list_filter = ("level",)
    search_fields = ("name","slug")

class BaseSingleInline(admin.StackedInline):
    extra = 0; max_num = 1; can_delete = True

class InvestmentDetailsInline(BaseSingleInline): model = InvestmentDetails
class CashDetailsInline(BaseSingleInline): model = CashDetails
class RealEstateDetailsInline(BaseSingleInline): model = RealEstateDetails
class PreciousMetalDetailsInline(BaseSingleInline): model = PreciousMetalDetails
class CollectibleDetailsInline(BaseSingleInline): model = CollectibleDetails
class OtherDetailsInline(BaseSingleInline): model = OtherDetails

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("name","account","category","type","currency","is_active","created_at")
    list_filter = ("category","is_active","currency","type__level","account__type")
    search_fields = ("name","account__name","account__owner__username","account__owner__email")
    autocomplete_fields = ("account","type")
    def get_inlines(self, request, obj=None):
        if not obj:
            return [ CashDetailsInline, InvestmentDetailsInline,
                    RealEstateDetailsInline, PreciousMetalDetailsInline, CollectibleDetailsInline, OtherDetailsInline]
        from .models import AssetCategory
        mapping = {
            AssetCategory.CASH: [CashDetailsInline],
            AssetCategory.INVESTMENT: [InvestmentDetailsInline],
            AssetCategory.REAL_ESTATE: [RealEstateDetailsInline],
            AssetCategory.PRECIOUS_METAL: [PreciousMetalDetailsInline],
            AssetCategory.COLLECTIBLE: [CollectibleDetailsInline],
            AssetCategory.OTHER: [OtherDetailsInline],
        }
        return mapping.get(obj.category, [])

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("asset","txn_type","timestamp","quantity","amount","fee","memo")
    list_filter = ("txn_type",)
    search_fields = ("asset__name","memo")
    autocomplete_fields = ("asset",)

