"""Distinguish missing provider prices from invalid requests or free execution."""


class PriceQuoteRequired(ValueError):
    """A provider's price depends on an account, usage, or unverified tariff."""
