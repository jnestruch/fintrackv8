from django.contrib import admin
from .models import Instrument, InstrumentKind, Exchange, Listing, Network, Token, PriceSource, Quote

@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "isin", "currency", "active")
    list_filter = ("kind", "active", "currency")
    search_fields = ("name", "isin")

@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ("mic", "name", "country", "timezone")
    search_fields = ("mic", "name")

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("ticker", "exchange", "instrument", "primary")
    list_filter = ("exchange", "primary")
    search_fields = ("ticker", "instrument__name", "exchange__mic")
    autocomplete_fields = ("instrument", "exchange")

@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ("symbol", "network", "instrument", "contract_address")
    list_filter = ("network",)
    search_fields = ("symbol", "contract_address", "instrument__name")
    autocomplete_fields = ("instrument", "network")

@admin.register(PriceSource)
class PriceSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("instrument", "listing", "token", "source", "ts", "price", "currency")
    list_filter = ("source", "currency")
    search_fields = ("instrument__name", "listing__ticker", "token__symbol")
    autocomplete_fields = ("instrument", "listing", "token", "source")
