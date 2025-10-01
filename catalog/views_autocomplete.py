from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Listing, Token

@login_required
def listing_search(request):
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    qs = Listing.objects.select_related("instrument", "exchange").all()
    if q:
        qs = qs.filter(Q(ticker__icontains=q) | Q(instrument__name__icontains=q) | Q(exchange__mic__icontains=q))
    paginator = Paginator(qs.order_by("ticker"), 20)
    page_obj = paginator.get_page(page)
    results = [{"id": x.id, "text": f"{x.ticker} — {x.instrument.name} @ {x.exchange.mic}"} for x in page_obj]
    return JsonResponse({"results": results, "pagination": {"more": page_obj.has_next()}})

@login_required
def token_search(request):
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    qs = Token.objects.select_related("instrument", "network").all()
    if q:
        qs = qs.filter(Q(symbol__icontains=q) | Q(instrument__name__icontains=q) | Q(network__code__icontains=q) | Q(contract_address__icontains=q))
    paginator = Paginator(qs.order_by("symbol"), 20)
    page_obj = paginator.get_page(page)
    def label(t):
        s = f"{t.symbol} — {t.instrument.name} @ {t.network.code}"
        return s + (f" ({t.contract_address[:10]}…)" if t.contract_address else "")
    results = [{"id": x.id, "text": label(x)} for x in page_obj]
    return JsonResponse({"results": results, "pagination": {"more": page_obj.has_next()}})
