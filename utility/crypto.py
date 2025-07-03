import requests
import re

def get_crypto_rate(ticker, curr='usd'):
    _ = requests.get(f"https://www.coingecko.com/en/search_v2?query={ticker}&vs_currency={curr}").json()
    if 'status' in _ and _['status'] != '200': return False
    if len(_['coins']) < 1: return False
    return {
        "name": _['coins'][0]['name'],
        "cc": _['coins'][0]['symbol'],
        "price": float(re.sub(r'[^\d.]', '', _['coins'][0]['data']['price'])),
        '24h_change': float(_['coins'][0]['data']['price_change_percentage_24h']['usd'])
    }