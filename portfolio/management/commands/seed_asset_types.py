from django.core.management.base import BaseCommand
from portfolio.models import AssetType

def add(name, level, parent=None, slug=None):
    obj, _ = AssetType.objects.get_or_create(
        slug=(slug or name.lower().replace(" ", "-")),
        defaults={"name": name, "level": level, "parent": parent},
    )
    return obj

class Command(BaseCommand):
    help = "Seed the 3-level AssetCategory taxonomy"
    def handle(self, *args, **kwargs):
        #L1
        cash = add("Cash", 1)
        investment = add("Investment", 1)
        real_estate = add("Real estate", 1, slug="real-estate")
        collectibles = add("Collectibles", 1)
        precious = add("Precious metals", 1, slug="precious-metals")
        other = add("Other", 1)

        # L2
        stock = add("Stock", 2, parent=investment)
        etf = add("ETF", 2, parent=investment)
        crypto = add("Crypto", 2, parent=investment)

        # L3
        add("US Stocks", 3, parent=stock, slug="us-stocks")
        add("EU Stocks", 3, parent=stock, slug="eu-stocks")


        self.stdout.write(self.style.SUCCESS("Asset types seeded."))
