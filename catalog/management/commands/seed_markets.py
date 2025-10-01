from django.core.management.base import BaseCommand
from catalog.models import Instrument, InstrumentKind, Exchange, Listing, Network, Token

class Command(BaseCommand):
    help = "Seed minimal exchanges/networks and sample instruments"

    def handle(self, *args, **kwargs):
        xnas, _ = Exchange.objects.get_or_create(mic="XNAS", defaults={"name":"NASDAQ","country":"US","timezone":"America/New_York"})
        xnys, _ = Exchange.objects.get_or_create(mic="XNYS", defaults={"name":"NYSE","country":"US","timezone":"America/New_York"})
        btc, _ = Network.objects.get_or_create(code="BTC", defaults={"name":"Bitcoin"})
        eth, _ = Network.objects.get_or_create(code="ETH", defaults={"name":"Ethereum"})

        aapl, _ = Instrument.objects.get_or_create(kind=InstrumentKind.EQUITY, name="Apple Inc.", defaults={"isin":"US0378331005","currency":"USD"})
        Listing.objects.get_or_create(instrument=aapl, exchange=xnas, ticker="AAPL", defaults={"primary": True})

        ivv, _  = Instrument.objects.get_or_create(kind=InstrumentKind.ETF, name="iShares Core S&P 500 ETF", defaults={"isin":"US4642872000","currency":"USD"})
        Listing.objects.get_or_create(instrument=ivv, exchange=xnys, ticker="IVV", defaults={"primary": True})

        btc_inst, _ = Instrument.objects.get_or_create(kind=InstrumentKind.CRYPTO, name="Bitcoin", defaults={"currency":"EUR"})
        Token.objects.get_or_create(instrument=btc_inst, network=btc, symbol="BTC", contract_address="")

        eth_inst, _ = Instrument.objects.get_or_create(kind=InstrumentKind.CRYPTO, name="Ethereum", defaults={"currency":"EUR"})
        Token.objects.get_or_create(instrument=eth_inst, network=eth, symbol="ETH", contract_address="")

        self.stdout.write(self.style.SUCCESS("Markets seeded."))
