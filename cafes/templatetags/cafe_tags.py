from decimal import Decimal

from django import template

register = template.Library()

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


@register.filter
def money(amount, cafe):
    """Format a price in the café's currency: '$3', '$3.50', or 'KES 250' when there's no symbol."""
    if amount is None:
        return ""
    amount = Decimal(amount)
    text = f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"
    symbol = CURRENCY_SYMBOLS.get(cafe.currency)
    return f"{symbol}{text}" if symbol else f"{cafe.currency} {text}"
