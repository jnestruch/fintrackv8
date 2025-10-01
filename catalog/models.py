from django.db import models

class InstrumentKind(models.TextChoices):
    EQUITY = "EQUITY", "Equity"
    ETF    = "ETF", "ETF"
    CRYPTO = "CRYPTO", "Crypto"
    # extend later (BOND, FUND, OPTION, FUTURE, FX, ...)

class Instrument(models.Model):
    kind = models.CharField(max_length=16, choices=InstrumentKind.choices)
    name = models.CharField(max_length=200)           # Apple Inc., Bitcoin, ...
    isin = models.CharField(max_length=12, blank=True) # International Securities Identification Number
    currency = models.CharField(max_length=3, blank=True) # ISO 4217 currency code, e.g., USD, EUR, BTC
    sector = models.CharField(max_length=64, blank=True) # Technology, Financial Services, ...
    active = models.BooleanField(default=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta: 
        indexes = [models.Index(fields=["kind", "active"])]

    def __str__(self): 
        return f"{self.name} ({self.kind})"

class Exchange(models.Model):
    mic = models.CharField(max_length=10, unique=True)  # ISO 10383 MIC, e.g., XNAS
    name = models.CharField(max_length=120)             # NASDAQ
    country = models.CharField(max_length=2, blank=True) # US
    timezone = models.CharField(max_length=64, blank=True) # America/New_York

    def __str__(self): 
        return f"{self.name} ({self.mic})"

class Listing(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="listings") # what is listed
    exchange = models.ForeignKey(Exchange, on_delete=models.PROTECT, related_name="listings") # where it's traded
    ticker = models.CharField(max_length=32)               # AAPL, MSFT, BTC-USD, ...
    primary = models.BooleanField(default=False)

    class Meta:
        unique_together = [("exchange", "ticker")]
        indexes = [models.Index(fields=["ticker"])]

    def __str__(self): 
        return f"{self.ticker} @ {self.exchange.mic}"

class Network(models.Model):
    code = models.CharField(max_length=32, unique=True)  # BTC, ETH, SOL
    name = models.CharField(max_length=64)            # Bitcoin, Ethereum, Solana

    def __str__(self): 
        return self.name

class Token(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="tokens")
    network = models.ForeignKey(Network, on_delete=models.PROTECT, related_name="tokens")
    symbol = models.CharField(max_length=32)              # BTC, ETH, USDC, SOL
    contract_address = models.CharField(max_length=128, blank=True) # for tokens on smart contract platforms, blank for native coins

    class Meta:
        unique_together = [("network", "symbol"), ("network", "contract_address")]
        indexes = [models.Index(fields=["symbol"])]

    def __str__(self):
        return f"{self.symbol} @ {self.network.code}" + (f" ({self.contract_address[:10]}…)" if self.contract_address else "")

class PriceSource(models.Model):
    code = models.CharField(max_length=40, unique=True) # e.g., "yahoo_finance", "coin_gecko", COINBASE, ...
    name = models.CharField(max_length=120)

    def __str__(self): 
        return self.code

class Quote(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, null=True, blank=True, on_delete=models.CASCADE)
    token = models.ForeignKey(Token, null=True, blank=True, on_delete=models.CASCADE)
    source = models.ForeignKey(PriceSource, on_delete=models.PROTECT)
    ts = models.DateTimeField()
    price = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=3)

    class Meta:
        indexes = [models.Index(fields=["instrument", "ts"]),
                   models.Index(fields=["listing", "ts"]),
                   models.Index(fields=["token", "ts"])]
        
        unique_together = [("source", "listing", "token", "ts")]
