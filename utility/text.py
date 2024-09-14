import re
from utility.statics import NUMBERREGEX

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

def find_command_in_alias(command, commands_dict):
    for key, value in commands_dict.items():
        if 'alias' in value and command in value['alias']:
            return key
    return None

# Unwrap the K value
def unwrap_number(number):
    matches = re.search(NUMBERREGEX, number)
    amount_k = len(match.group(2)) if match.group(2) else 0
    amount_unwrapped = float(match.group(1))
    if amount_k > 0:
        amount_unwrapped = amount_unwrapped * (1000 ** amount_k)
    
    return amount_unwrapped