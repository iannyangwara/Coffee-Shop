from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def money(amount, cafe):
    """Format a price in the café's currency: 'KES 250' or 'KES 249.50'."""
    if amount is None:
        return ""
    amount = Decimal(amount)
    text = f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"
    return f"{cafe.currency} {text}"
