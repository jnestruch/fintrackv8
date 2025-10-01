from django.urls import path
from .views import (
    AssetListView, AssetDetailView,
    AssetCreateCategoryView, AssetCreateWithCategoryView,
    AssetUpdateView, AssetDeleteView,
    TransactionListView, TransactionCreateView, TransactionUpdateView, TransactionDeleteView, PortfolioOverviewView
)
from .views_autocomplete import listing_search, token_search

app_name = "portfolio"

urlpatterns = [
    path("", AssetListView.as_view(), name="asset_list"),
    path("overview/", PortfolioOverviewView.as_view(), name="overview"),
    path("new/", AssetCreateCategoryView.as_view(), name="asset_create_category"),
    path("new/<str:category>/", AssetCreateWithCategoryView.as_view(), name="asset_create_with_category"),
    path("<int:pk>/", AssetDetailView.as_view(), name="asset_detail"),
    path("<int:pk>/edit/", AssetUpdateView.as_view(), name="asset_edit"),
    path("<int:pk>/delete/", AssetDeleteView.as_view(), name="asset_delete"),
    path("<int:asset_pk>/transactions/", TransactionListView.as_view(), name="transaction_list"),
    path("<int:asset_pk>/transactions/new/", TransactionCreateView.as_view(), name="transaction_create"),
    path("<int:asset_pk>/transactions/<int:pk>/edit/", TransactionUpdateView.as_view(), name="transaction_edit"),
    path("<int:asset_pk>/transactions/<int:pk>/delete/", TransactionDeleteView.as_view(), name="transaction_delete"),
    path("autocomplete/listings/", listing_search, name="autocomplete_listings"),
    path("autocomplete/tokens/", token_search, name="autocomplete_tokens"),
]
