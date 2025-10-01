from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import (
    Instrument, InstrumentKind,
    Exchange, Listing,
    Network, Token,
    PriceSource, Quote,
)


EXCHANGES = [
    # MIC,            Name,                Country, Timezone
    ("XNAS",          "NASDAQ",            "US",    "America/New_York"),
    ("XNYS",          "New York Stock Exchange", "US", "America/New_York"),
    ("XETR",          "XETRA",             "DE",    "Europe/Berlin"),
    ("XLON",          "London Stock Exchange", "GB", "Europe/London"),
]

NETWORKS = [
    # Code,  Name
    ("BTC",  "Bitcoin"),
    ("ETH",  "Ethereum"),
    ("SOL",  "Solana"),
]

INSTRUMENTS = [
    # kind,               name,                                  isin (optional), currency
    (InstrumentKind.EQUITY, "Apple Inc.",                         "US0378331005", "USD"),
    (InstrumentKind.EQUITY, "Microsoft Corporation",              "US5949181045", "USD"),
    (InstrumentKind.ETF,    "iShares Core S&P 500 ETF",           "US4642872000", "USD"),
    (InstrumentKind.ETF,    "Vanguard FTSE All-World UCITS ETF",  "IE00B3RBWM25", "USD"),
    (InstrumentKind.CRYPTO, "Bitcoin",                            "",             "USD"),
    (InstrumentKind.CRYPTO, "Ethereum",                           "",             "USD"),
    (InstrumentKind.CRYPTO, "USD Coin",                           "",             "USD"),
]

LISTINGS = [
    # instrument_name,                 MIC,   ticker, primary
    ("Apple Inc.",                      "XNAS", "AAPL", True),
    ("Microsoft Corporation",           "XNAS", "MSFT", True),
    ("iShares Core S&P 500 ETF",        "XNYS", "IVV",  True),
    ("Vanguard FTSE All-World UCITS ETF","XLON","VWRL", True),
    ("Vanguard FTSE All-World UCITS ETF","XETR","VWRL", False),  # example secondary venue
]

TOKENS = [
    # instrument_name,  network_code, symbol, contract (blank for native)
    ("Bitcoin",         "BTC",         "BTC",   ""),
    ("Ethereum",        "ETH",         "ETH",   ""),
    ("USD Coin",        "ETH",         "USDC",  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
    ("USD Coin",        "SOL",         "USDC",  ""),  # Solana native representation (example)
]

PRICE_SOURCES = [
    # code,     name
    ("YF",      "Yahoo Finance"),
    ("ALPACA",  "Alpaca Markets"),
    ("COINBASE","Coinbase"),
]


class Command(BaseCommand):
    help = "Seed the catalog: exchanges, networks, instruments, listings, tokens, price sources (optional quotes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing data in catalog tables before seeding (DANGEROUS in prod).",
        )
        parser.add_argument(
            "--with-quotes",
            action="store_true",
            help="Also create a few sample Quote rows for demo purposes.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            self._reset_all()

        # 1) Exchanges
        ex_by_mic = {}
        for mic, name, country, tz in EXCHANGES:
            ex, _ = Exchange.objects.get_or_create(
                mic=mic,
                defaults={"name": name, "country": country, "timezone": tz},
            )
            # update minimal fields if changed (idempotent)
            updated = False
            if ex.name != name:
                ex.name = name; updated = True
            if ex.country != country:
                ex.country = country; updated = True
            if ex.timezone != tz:
                ex.timezone = tz; updated = True
            if updated:
                ex.save()
            ex_by_mic[mic] = ex
        self.stdout.write(self.style.SUCCESS(f"Exchanges seeded: {len(ex_by_mic)}"))

        # 2) Networks
        net_by_code = {}
        for code, name in NETWORKS:
            net, _ = Network.objects.get_or_create(code=code, defaults={"name": name})
            if net.name != name:
                net.name = name; net.save()
            net_by_code[code] = net
        self.stdout.write(self.style.SUCCESS(f"Networks seeded: {len(net_by_code)}"))

        # 3) Instruments
        inst_by_name = {}
        for kind, name, isin, ccy in INSTRUMENTS:
            inst, _ = Instrument.objects.get_or_create(
                name=name,
                kind=kind,
                defaults={"isin": (isin or ""), "currency": (ccy or ""), "active": True},
            )
            # If existing, keep it up-to-date
            changed = False
            if isin and inst.isin != isin:
                inst.isin = isin; changed = True
            if ccy and inst.currency != ccy:
                inst.currency = ccy; changed = True
            if not inst.active:
                inst.active = True; changed = True
            if changed:
                inst.save()
            inst_by_name[name] = inst
        self.stdout.write(self.style.SUCCESS(f"Instruments seeded: {len(inst_by_name)}"))

        # 4) Listings (equities/ETFs)
        listing_count = 0
        for inst_name, mic, ticker, primary in LISTINGS:
            inst = inst_by_name.get(inst_name)
            if not inst:
                self.stdout.write(self.style.WARNING(f"Skipping listing for unknown instrument: {inst_name}"))
                continue
            ex = ex_by_mic.get(mic)
            if not ex:
                self.stdout.write(self.style.WARNING(f"Skipping listing {ticker}: unknown MIC {mic}"))
                continue
            lst, created = Listing.objects.get_or_create(
                instrument=inst,
                exchange=ex,
                ticker=ticker,
                defaults={"primary": primary},
            )
            if not created and lst.primary != primary:
                lst.primary = primary; lst.save()
            listing_count += 1
        self.stdout.write(self.style.SUCCESS(f"Listings seeded: {listing_count}"))

        # 5) Tokens (crypto)
        token_count = 0
        for inst_name, net_code, symbol, contract in TOKENS:
            inst = inst_by_name.get(inst_name)
            if not inst:
                self.stdout.write(self.style.WARNING(f"Skipping token for unknown instrument: {inst_name}"))
                continue
            net = net_by_code.get(net_code)
            if not net:
                self.stdout.write(self.style.WARNING(f"Skipping token {symbol}: unknown network {net_code}"))
                continue
            tok, _ = Token.objects.get_or_create(
                instrument=inst, network=net, symbol=symbol,
                defaults={"contract_address": contract or ""},
            )
            # Update contract if changed
            if contract is not None and tok.contract_address != (contract or ""):
                tok.contract_address = (contract or ""); tok.save()
            token_count += 1
        self.stdout.write(self.style.SUCCESS(f"Tokens seeded: {token_count}"))

        # 6) Price sources
        src_by_code = {}
        for code, name in PRICE_SOURCES:
            src, _ = PriceSource.objects.get_or_create(code=code, defaults={"name": name})
            if src.name != name:
                src.name = name; src.save()
            src_by_code[code] = src
        self.stdout.write(self.style.SUCCESS(f"Price sources seeded: {len(src_by_code)}"))

        # 7) Optional: a couple of sample quotes
        if opts["with_quotes"]:
            self._seed_sample_quotes(inst_by_name, src_by_code)
            self.stdout.write(self.style.SUCCESS("Sample quotes created."))

        self.stdout.write(self.style.SUCCESS("Catalog seeding complete."))

    def _seed_sample_quotes(self, inst_by_name, src_by_code):
        """Create a few demo quotes at 'now' just so pages have data. Safe to run multiple times."""
        now = timezone.now()

        def upsert_quote(*, instrument=None, listing=None, token=None, source_code="YF", price=0.0, currency="USD"):
            src = src_by_code.get(source_code)
            if not src:
                return
            # Avoid duplicates on (source, listing, token, ts). We'll vary ts by seconds to keep unique_together happy.
            Quote.objects.get_or_create(
                instrument=instrument,
                listing=listing,
                token=token,
                source=src,
                ts=now,
                defaults={"price": price, "currency": currency},
            )

        # Apple via XNAS
        aapl = inst_by_name.get("Apple Inc.")
        if aapl:
            # prefer a listing if present
            lst = Listing.objects.filter(instrument=aapl).first()
            upsert_quote(instrument=aapl, listing=lst, price=210.00, currency="USD")

        # IVV ETF
        ivv = inst_by_name.get("iShares Core S&P 500 ETF")
        if ivv:
            lst = Listing.objects.filter(instrument=ivv).first()
            upsert_quote(instrument=ivv, listing=lst, price=520.00, currency="USD")

        # ETH token
        eth = inst_by_name.get("Ethereum")
        if eth:
            tok = Token.objects.filter(instrument=eth).first()
            upsert_quote(instrument=eth, token=tok, source_code="COINBASE", price=3000.00, currency="USD")

        # BTC token
        btc = inst_by_name.get("Bitcoin")
        if btc:
            tok = Token.objects.filter(instrument=btc).first()
            upsert_quote(instrument=btc, token=tok, source_code="COINBASE", price=60000.00, currency="USD")

    def _reset_all(self):
        """Delete all catalog data. This is destructive; intended for dev only."""
        self.stdout.write(self.style.WARNING("Resetting catalog tables..."))
        # Ordering: children before parents to satisfy FKs
        Quote.objects.all().delete()
        Listing.objects.all().delete()
        Token.objects.all().delete()
        PriceSource.objects.all().delete()
        Exchange.objects.all().delete()
        Network.objects.all().delete()
        Instrument.objects.all().delete()
        self.stdout.write(self.style.WARNING("Catalog tables cleared."))
