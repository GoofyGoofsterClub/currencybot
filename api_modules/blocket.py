import re
from json import loads
from requests import get
LINK_REGEX = r"(https?:\/\/www\.blocket\.se\/annons\/\w+\/(.*)\/(\d+))"

def regex_match(string):
    return re.match(LINK_REGEX, string)

def regex_find(string):
    return re.findall(LINK_REGEX, string)

def parse_price(url):

    # schizo
    token_req = get("https://www.blocket.se/api/adout-api-route/refresh-token-and-validate-session").json()

    listing_id = re.search(LINK_REGEX, url).group(3)

    r = get(f'https://api.blocket.se/search_bff/v2/content/{listing_id}',  headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": f"Bearer {token_req['bearerToken']}"
    })

    if (r.status_code != 200):
        return {
            'name': '???',
            'link': url,
            'currency': 'SEK',
            'price': 0,
            'delivery': None
        }

    r = r.json()

    product_name = r['data']['subject']
    price_whole = str(r['data']['price']['value'])
    price_fraction = 0
    price_currency = "SEK"

    return {
        'name': (product_name[:65] + '...') if len(product_name) > 65 else product_name,
        'link': url,
        'currency': price_currency,
        'price': float(price_whole.replace('.', '').replace(',', "")) + float(price_fraction)/100,
        'delivery': None
    }