from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView, DetailView, DeleteView
from django.urls import reverse_lazy
from .models import Asset, AssetType, AssetCategory
from .forms import (
    CategorySelectForm, AssetBaseForm, 
    InvestmentDetailsForm, CashDetailsForm, RealEstateDetailsForm, 
    PreciousMetalDetailsForm, CollectibleDetailsForm, OtherDetailsForm
)
from collections import defaultdict, OrderedDict
from decimal import Decimal
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.views.generic import TemplateView
from .forms import TransactionForm
from django.db.models import DecimalField
from .services import market_value_for_asset


# Helper mapping
DETAIL_FORM_BY_CATEGORY = {
    AssetCategory.CASH: CashDetailsForm,
    AssetCategory.REAL_ESTATE: RealEstateDetailsForm,
    AssetCategory.PRECIOUS_METAL: PreciousMetalDetailsForm,
    AssetCategory.COLLECTIBLE: CollectibleDetailsForm,
    AssetCategory.OTHER: OtherDetailsForm,
    # AssetCategory.INVESTMENT handled separately
}

def _save_non_investment(asset_form, detail_form, category):
    asset = asset_form.save(commit=False)
    asset.category = category
    asset.save()
    d = detail_form.save(commit=False); d.asset = asset; d.save()
    return asset

class AssetListView(LoginRequiredMixin, ListView):
    template_name = "portfolio/asset_list.html"; context_object_name = "assets"
    def get_queryset(self):
        qs = (Asset.objects.filter(account__owner=self.request.user)
              .select_related("account","type","type__parent","investment",
                              "cash","realestate","metal","collectible","other"))
        acc_id = self.request.GET.get("account")
        return qs.filter(account_id=acc_id) if acc_id else qs

class AssetDetailView(LoginRequiredMixin, DetailView):
    template_name = "portfolio/asset_detail.html"; context_object_name = "asset"
    def get_queryset(self):
        return Asset.objects.filter(account__owner=self.request.user).select_related(
            "account","type","type__parent","investment",
            "cash","realestate","metal","collectible","other")


# Step 1: pick category
class AssetCreateCategoryView(View):
    template_name = "portfolio/asset_category_select.html"
    def get(self, request): return render(request, self.template_name, {"form": CategorySelectForm()})
    def post(self, request):
        form = CategorySelectForm(request.POST)
        if form.is_valid():
            return redirect("portfolio:asset_create_with_category", category=form.cleaned_data["category"])
        return render(request, self.template_name, {"form": form})

# Step 2: form per category
class AssetCreateWithCategoryView(View):
    def get(self, request, category):
        base = AssetBaseForm()
        if category == AssetCategory.INVESTMENT:
            return render(request, "portfolio/asset_form_investment.html", {"asset_form": base, "inv_form": InvestmentDetailsForm(), "creating": True})
        # non-investment
        FormCls = DETAIL_FORM_BY_CATEGORY[category]
        return render(request, "portfolio/asset_form.html", {"asset_form": base, "detail_form": FormCls(), "category": category, "creating": True})

    def post(self, request, category):
        base = AssetBaseForm(request.POST)
        if category == AssetCategory.INVESTMENT:
            inv = InvestmentDetailsForm(request.POST)
            if base.is_valid() and inv.is_valid():
                asset = base.save(commit=False); asset.category = AssetCategory.INVESTMENT; asset.save()
                inv_obj = inv.save(commit=False); inv_obj.asset = asset; inv_obj.save()
                return redirect("portfolio:asset_detail", pk=asset.pk)
            return render(request, "portfolio/asset_form_investment.html", {"asset_form": base, "inv_form": inv, "creating": True})

        # non-investment branch
        FormCls = DETAIL_FORM_BY_CATEGORY[category]
        detail = FormCls(request.POST)
        if base.is_valid() and detail.is_valid():
            asset = _save_non_investment(base, detail, category)
            return redirect("portfolio:asset_detail", pk=asset.pk)
        return render(request, "portfolio/asset_form.html", {"asset_form": base, "detail_form": detail, "category": category, "creating": True})


# Edit
class AssetUpdateView(View):
    def get_object(self, pk): return get_object_or_404(Asset, pk=pk)

    def get(self, request, pk):
        asset = self.get_object(pk)
        base = AssetBaseForm(instance=asset)
        if asset.category == AssetCategory.INVESTMENT:
            inv = InvestmentDetailsForm(instance=asset.investment)
            # nice labels for select2 when editing
            if inv.instance and inv.instance.listing_id:
                lst = inv.instance.listing
                inv.fields["listing"].widget.attrs["data-current-text"] = f"{lst.ticker} — {lst.instrument.name} @ {lst.exchange.mic}"
            if inv.instance and inv.instance.token_id:
                tok = inv.instance.token
                label = f"{tok.symbol} — {tok.instrument.name} @ {tok.network.code}" + (f" ({tok.contract_address[:10]}…)" if tok.contract_address else "")
                inv.fields["token"].widget.attrs["data-current-text"] = label
            return render(request, "portfolio/asset_form_investment.html", {"asset_form": base, "inv_form": inv, "creating": False, "object": asset})

        # non-investment edit
        FormCls = DETAIL_FORM_BY_CATEGORY[asset.category]
        detail_inst = asset.detail
        return render(request, "portfolio/asset_form.html", {"asset_form": base, "detail_form": FormCls(instance=detail_inst), "category": asset.category, "creating": False, "object": asset})

    def post(self, request, pk):
        asset = self.get_object(pk)
        base = AssetBaseForm(request.POST, instance=asset)
        if asset.category == AssetCategory.INVESTMENT:
            inv = InvestmentDetailsForm(request.POST, instance=asset.investment)
            if base.is_valid() and inv.is_valid():
                base.save(); inv.save()
                return redirect("portfolio:asset_detail", pk=asset.pk)
            return render(request, "portfolio/asset_form_investment.html", {"asset_form": base, "inv_form": inv, "creating": False, "object": asset})

        # non-investment
        FormCls = DETAIL_FORM_BY_CATEGORY[asset.category]
        detail = FormCls(request.POST, instance=asset.detail)
        if base.is_valid() and detail.is_valid():
            base.save(); detail.save()
            return redirect("portfolio:asset_detail", pk=asset.pk)
        return render(request, "portfolio/asset_form.html", {"asset_form": base, "detail_form": detail, "category": asset.category, "creating": False, "object": asset})

# Ownership check mixin
class OwnerCheckMixin(UserPassesTestMixin):
    def test_func(self):
        obj = self.get_object(); return obj.account.owner_id == self.request.user.id

# Delete view for assets
class AssetDeleteView(LoginRequiredMixin, OwnerCheckMixin, DeleteView):
    model = Asset; success_url = reverse_lazy("portfolio:asset_list")
    template_name = "portfolio/asset_confirm_delete.html"
    def get_queryset(self): return Asset.objects.filter(account__owner=self.request.user)

# Transactions
class TransactionListView(LoginRequiredMixin, ListView):
    template_name = "portfolio/transaction_list.html"; context_object_name = "transactions"
    def get_queryset(self):
        asset = get_object_or_404(Asset.objects.filter(account__owner=self.request.user), pk=self.kwargs["asset_pk"])
        self.asset = asset; return asset.transactions.select_related("asset")
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); ctx["asset"] = getattr(self, "asset", None); return ctx

class TransactionCreateView(LoginRequiredMixin, View):
    template_name = "portfolio/transaction_form.html"
    def get(self, request, asset_pk):
        asset = get_object_or_404(Asset.objects.filter(account__owner=self.request.user), pk=asset_pk)
        return render(request, self.template_name, {"form": TransactionForm(), "asset": asset})
    def post(self, request, asset_pk):
        asset = get_object_or_404(Asset.objects.filter(account__owner=self.request.user), pk=asset_pk)
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False); txn.asset = asset; txn.save()
            return redirect("portfolio:transaction_list", asset_pk=asset.pk)
        return render(request, self.template_name, {"form": form, "asset": asset})

class TransactionUpdateView(LoginRequiredMixin, View):
    template_name = "portfolio/transaction_form.html"
    def _get(self, request, asset_pk, pk):
        asset = get_object_or_404(Asset.objects.filter(account__owner=self.request.user), pk=asset_pk)
        txn = get_object_or_404(asset.transactions, pk=pk)
        return txn, asset
    def get(self, request, asset_pk, pk):
        txn, asset = self._get(request, asset_pk, pk)
        return render(request, self.template_name, {"form": TransactionForm(instance=txn), "asset": asset})
    def post(self, request, asset_pk, pk):
        txn, asset = self._get(request, asset_pk, pk)
        form = TransactionForm(request.POST, instance=txn)
        if form.is_valid():
            form.save(); return redirect("portfolio:transaction_list", asset_pk=asset.pk)
        return render(request, self.template_name, {"form": form, "asset": asset})

class TransactionDeleteView(LoginRequiredMixin, View):
    template_name = "portfolio/transaction_confirm_delete.html"
    def _get(self, request, asset_pk, pk):
        asset = get_object_or_404(Asset.objects.filter(account__owner=self.request.user), pk=asset_pk)
        txn = get_object_or_404(asset.transactions, pk=pk)
        return txn, asset
    def get(self, request, asset_pk, pk):
        txn, asset = self._get(request, asset_pk, pk)
        return render(request, self.template_name, {"txn": txn, "asset": asset})
    def post(self, request, asset_pk, pk):
        txn, asset = self._get(request, asset_pk, pk)
        txn.delete(); return redirect("portfolio:transaction_list", asset_pk=asset.pk)

class PortfolioOverviewView(LoginRequiredMixin, TemplateView):
    template_name = "portfolio/overview.html"

    def get_queryset(self):
        return (
            Asset.objects
            .filter(account__owner=self.request.user)
            # .select_related("account", "type")
            .select_related("account", "type", "investment", "investment__listing__exchange",
                            "investment__token__network", "metal")
            .annotate(
                balance=Coalesce(
                    Sum("transactions__amount"),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=20, decimal_places=2)),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            )
            .order_by("account__name", "name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        assets = list(self.get_queryset())

        # Build a list of accounts with their assets and per-account totals (by currency)
        accounts_view = []
        grand_totals = defaultdict(Decimal)
        grand_bal_totals = defaultdict(Decimal)  # by asset currency (no FX)
        grand_mv_totals = defaultdict(Decimal)   # by MV currency (no FX)
        grouped = OrderedDict()

        # for a in assets:
        #     grouped.setdefault(a.account.name, []).append(a)

        # for acc_name, acc_assets in grouped.items():
        #     totals_by_ccy = defaultdict(Decimal)
        #     for a in acc_assets:
        #         amt = a.balance or Decimal("0")
        #         totals_by_ccy[a.currency] += amt
        #         grand_totals[a.currency] += amt

        #     accounts_view.append({
        #         "name": acc_name,
        #         "assets": acc_assets,
        #         "totals": dict(sorted(totals_by_ccy.items())),
        #     })

        # Compute MV for each asset once (avoid repeated queries in template)
        enriched = []
        for a in assets:
            mv, mv_ccy = market_value_for_asset(a)
            enriched.append((a, mv, mv_ccy))

        # Group by account
        for a, mv, mv_ccy in enriched:
            grouped.setdefault(a.account.name, []).append((a, mv, mv_ccy))

        # Build per-account sections and totals
        for acc_name, acc_rows in grouped.items():
            totals_bal = defaultdict(Decimal)  # by asset currency
            totals_mv = defaultdict(Decimal)   # by MV currency
            # rows for template
            rows = []
            for a, mv, mv_ccy in acc_rows:
                # Update balance totals
                bal_ccy = a.currency
                bal_amt = a.balance or Decimal("0")
                totals_bal[bal_ccy] += bal_amt
                grand_bal_totals[bal_ccy] += bal_amt

                # Update MV totals
                if mv is not None and mv_ccy:
                    totals_mv[mv_ccy] += mv
                    grand_mv_totals[mv_ccy] += mv

                rows.append({
                    "asset": a,
                    "balance": bal_amt,
                    "balance_currency": bal_ccy,
                    "market_value": mv,
                    "market_currency": mv_ccy,
                })

            accounts_view.append({
                "name": acc_name,
                "rows": rows,
                "totals_balance": dict(sorted(totals_bal.items())),
                "totals_market": dict(sorted(totals_mv.items())),
            })


        ctx.update({
            "accounts": accounts_view,                       # list of {name, assets, totals}
            "grand_totals": dict(sorted(grand_totals.items())),  # {ccy: total}
            "grand_bal_totals": dict(sorted(grand_bal_totals.items())),
            "grand_mv_totals": dict(sorted(grand_mv_totals.items())),
        })
        return ctx