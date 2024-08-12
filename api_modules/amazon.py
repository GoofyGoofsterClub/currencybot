import re
import requests
import time
import json

pattern = r'https:\/\/www\.amazon\.((\w+)(\.\w+)?)(\/.*)?\/(dp|product)\/(\w+)'
swatch_pattern = r'<spanclass=\"a-size-minitwisterSwatchPrice\">(.*)(<\/span><\/span>)'
swatch_specific_pattern = r'<spanclass=\"a-size-miniolpWrapper\">(.*)<\/span></span>'
specific_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def regex(url):
    if re.findall(pattern, url):
        regex_match = list(re.findall(pattern, url))

        results = []

        for match in regex_match:
            product_name = get_product_name("amazon.{}".format(match[0]), match[5])
            results.append({
                "domain": "amazon.{}".format(match[0]),
                "product_name": product_name,
                "asin": match[5]
            })
        
        return results
    return False

def get_product_name(domain, asin):
    request_data = requests.get("https://{}/-/en/dp/{}".format(
        domain,
        asin
    ), headers=specific_headers)

    # amazon.se has a protection against automated requests, absolute goofsters.
    if (request_data.status_code != 200):
        time.sleep(0.1)
        return get_product_name(domain, asin)

    match = re.search(r'<title>(.*?)<\/title>', request_data.text)

    del request_data

    if match:
        return match.group(1)
    else:
        return '(Name couldn\'t be retrieved)'
    

def get_pricing_info(domain, asin):
    domain_formatted = "https://{2}/gp/twister/dimension?isDimensionSlotsAjax=1&asinList={0}&vs=1&productTypeDefinition=INTERNAL_MEMORY&productGroupId=ce_display_on_website&parentAsin={0}&isPrime=0&qid={1}&sr=8-1&isOneClickEnabled=0&originalHttpReferer=https://amazon.com&keywords=&landingAsin={0}&deviceType=web&showFancyPrice=true&twisterFlavor=twisterPlusDesktopConfigurator".format(asin, round(time.time()), domain)
    print(domain_formatted)
    request_data = requests.post(domain_formatted, headers=specific_headers)

    # amazon.se has a protection against automated requests, absolute goofsters.
    if request_data.status_code != 200:
        time.sleep(0.1)
        return get_pricing_info(domain, asin)

    json_data = json.loads(request_data.text)
    price = json_data['Value']['content']['twisterSlotJson']['price']
    if 'isAvailable' in json_data['Value']['content']['twisterSlotJson']:
        is_available = json_data['Value']['content']['twisterSlotJson']['isAvailable']
    else:
        is_available = None
    
    unfetched_price_text = None
    try:
        unfetched_price = re.findall(swatch_pattern,
                                 json_data['Value']['content']['twisterSlotDiv'].replace(" ", "").replace(",", "").replace("\\xa", ""))[0][0]
        currency_symbol = ''.join([i for i in unfetched_price if not i.isdigit()]).replace('Â', '').strip()
    except:
        unfetched_price = None
        currency_symbol = None
        unfetched_price_text = re.findall(swatch_specific_pattern, json_data['Value']['content']['twisterSlotDiv'].replace(" ", "").replace(",", "").replace("\\xa", ""))[0]
    
    return {
        'url': 'https://{}/dp/{}'.format(domain, asin),
        'price': price,
        'currency_symbol': currency_symbol,
        'is_available': is_available,
        'unfetched_price_text': unfetched_price_text if unfetched_price_text else ''
    }