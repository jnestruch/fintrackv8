# portfolio/views_autocomplete.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator

from .models import Listing, Token

@login_required
def listing_search(request):
    """
    Select2 AJAX for equities/ETFs listings.
    Query params:
      q: search string
      page: page number (1-based)
    Returns: { results: [{id, text}], pagination: {more: bool} }
    """
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    qs = (Listing.objects
          .select_related("instrument", "exchange")
          .all())
    if q:
        qs = qs.filter(
            Q(ticker__icontains=q) |
            Q(instrument__name__icontains=q) |
            Q(exchange__mic__icontains=q)
        )
    qs = qs.order_by("ticker")  # simple deterministic order

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(page)

    def fmt(item: Listing):
        # e.g. "AAPL — Apple Inc. @ XNAS"
        return f"{item.ticker} — {item.instrument.name} @ {item.exchange.mic}"

    results = [{"id": item.id, "text": fmt(item)} for item in page_obj.object_list]
    return JsonResponse({
        "results": results,
        "pagination": {"more": page_obj.has_next()},
    })


@login_required
def token_search(request):
    """
    Select2 AJAX for crypto tokens.
    Query params:
      q: search string
      page: page number (1-based)
    """
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    qs = (Token.objects
          .select_related("instrument", "network")
          .all())
    if q:
        qs = qs.filter(
            Q(symbol__icontains=q) |
            Q(instrument__name__icontains=q) |
            Q(network__code__icontains=q) |
            Q(contract_address__icontains=q)
        )
    qs = qs.order_by("symbol")

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(page)

    def fmt(item: Token):
        # e.g. "ETH — Ethereum @ ETH" or "UNI — Uniswap @ ETH (0x1234…)"
        suffix = f" @ {item.network.code}"
        if item.contract_address:
            suffix += f" ({item.contract_address[:10]}…)"
        return f"{item.symbol} — {item.instrument.name}{suffix}"

    results = [{"id": item.id, "text": fmt(item)} for item in page_obj.object_list]
    return JsonResponse({
        "results": results,
        "pagination": {"more": page_obj.has_next()},
    })
