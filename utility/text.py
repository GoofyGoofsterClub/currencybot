import re

def find_currency(currency, currencies):
    if not currency.strip():
        return None
    
    currency = currency.lower()

    for c in currencies:
        if c['cc'] == currency:
            return c
        if any([re.match(alias, currency) for alias in c['aliases']]):
            return c
    return None

def does_text_contain_currency(text, currencies):
    for c in currencies:
        if c['cc'] in text:
            return c
    return False
