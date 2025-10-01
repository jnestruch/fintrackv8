from django.urls import path
from .views_autocomplete import listing_search, token_search

app_name = "catalog"
urlpatterns = [
    path("autocomplete/listings/", listing_search, name="autocomplete_listings"),
    path("autocomplete/tokens/", token_search, name="autocomplete_tokens"),
]
