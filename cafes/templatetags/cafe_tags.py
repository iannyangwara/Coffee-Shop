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


@register.filter
def percent_of(value, peak):
    """How big `value` is next to `peak`, as a 0–100 number for bar widths and heights."""
    try:
        peak = float(peak)
        return round(max(0.0, min(100.0, float(value) / peak * 100)), 1) if peak else 0
    except (TypeError, ValueError):
        return 0


@register.filter
def hours_minutes(duration):
    """A timedelta as '7 h 05 min'."""
    if duration is None:
        return ""
    minutes = max(0, round(duration.total_seconds() / 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"
