import re
from json import loads
from requests import get
from bs4 import BeautifulSoup
LINK_REGEX = r"http(s)?:\/\/(www\.)?amazon((\.(\w+))?\.(\w+))\/(-\/)?([a-z]{2}\/)?((.*)\/)?dp\/(\w+)"

def regex_match(string):
    return re.match(LINK_REGEX, string)

def regex_find(string):
    return re.findall(LINK_REGEX, string)

def parse_price(url):
    url = '/'.join(url.split('/')[:-1] + [url.split('/')[-1].upper()])

    r = get(url,  headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    })
    b = BeautifulSoup(r.text, 'html.parser')
    product_name = b.find('span', id="productTitle").string.strip()
    price_whole = b.find_all('span', 'a-price-whole')[0].get_text()
    price_fraction = b.find_all('span', 'a-price-fraction')[0].string or 0
    whateverthefuck_bucket = b.find_all('div', 'cardRoot bucket')[0]
    price_currency_data = loads(whateverthefuck_bucket['data-components'] or '{"currencyCode": "USD"}')
    price_currency = price_currency_data['1']['price']['currencyCode']
    delivery_info = b.find_all('div', id="mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE")[0]
    delivery_info = delivery_info.find_all('span')[0]
    delivery_info = {
        'time': delivery_info['data-csa-c-delivery-time'],
        'price': float(re.sub(r'[^0-9.]', '', delivery_info['data-csa-c-delivery-price']) or 0)
    }

    return {
        'name': (product_name[:65] + '...') if len(product_name) > 65 else product_name,
        'link': url,
        'currency': price_currency,
        'price': float(price_whole.replace('.', '').replace(',', "")) + float(price_fraction)/100,
        'delivery': delivery_info
    }