import re
from json import loads
from requests import get
from bs4 import BeautifulSoup

LINK_REGEX = r"https://auktion\.kronofogden\.se/auk/w\.object\?[^ ]+"

def regex_match(string):
    return re.match(LINK_REGEX, string)

def regex_find(string):
    return re.findall(LINK_REGEX, string)

def parse_price(url):
    try:
        r = get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        })
        r.raise_for_status()

        b = BeautifulSoup(r.text, 'html.parser')
        product_name = b.find('h1')
        product_name = product_name.get_text(strip=True) if product_name else "Unnamed Product"

        price_tag = b.find('h3')
        price_span = b.find_all('span', class_='nico3')[1].get_text(strip=True)

        price_numeric = float(re.sub(r'[^\d,]', '', price_span).replace(',', '.'))

        return {
            'name': (product_name[:65] + '...') if len(product_name) > 65 else product_name,
            'link': url,
            'currency': 'SEK',
            'price': price_numeric,
            'delivery': None
        }

    except Exception as e:
        print(f"[ERROR] Failed to parse {url}: {e}")
        return None
