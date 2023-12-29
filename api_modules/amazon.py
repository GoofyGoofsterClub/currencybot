import re
import requests
import time
import json

pattern = r'https:\/\/www\.amazon\.((\w+)(\.\w+)?)\/(.*)/dp/(\w+)'
swatch_pattern = r'<spanclass=\"a-size-minitwisterSwatchPrice\">(.*)(<\/span><\/span>)'
specific_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def regex(url):
    if re.match(pattern, url):
        regex_match = list(re.findall(pattern, url))

        results = []

        for match in regex_match:
            product_name = get_product_name("amazon.{}".format(match[0]), match[4])

            results.append({
                "domain": "amazon.{}".format(match[0]),
                "product_name": product_name,
                "asin": match[4]
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
        print(request_data.text)
        time.sleep(0.1)
        return get_product_name(domain, asin)

    match = re.search(r'<title>(.*?)<\/title>', request_data.text)

    del request_data

    if match:
        return match.group(1)
    else:
        return '(Name couldn\'t be retrieved)'
    

def get_pricing_info(domain, asin):
    request_data = requests.post("https://{2}/gp/twister/dimension?isDimensionSlotsAjax=1&asinList={0}&vs=1&productTypeDefinition=INTERNAL_MEMORY&productGroupId=ce_display_on_website&parentAsin={0}&isPrime=0&qid={1}&sr=8-1&isOneClickEnabled=0&originalHttpReferer=https://amazon.com&keywords=&landingAsin={0}&deviceType=web&showFancyPrice=true&twisterFlavor=twisterPlusDesktopConfigurator".format(asin, round(time.time()), domain), headers=specific_headers)

    # amazon.se has a protection against automated requests, absolute goofsters.
    if request_data.status_code != 200:
        time.sleep(0.1)
        return get_pricing_info(domain, asin)

    json_data = json.loads(request_data.text)
    price = json_data['Value']['content']['twisterSlotJson']['price']
    is_available = json_data['Value']['content']['twisterSlotJson']['isAvailable']
    
    unfetched_price = re.findall(swatch_pattern,
                                 json_data['Value']['content']['twisterSlotDiv'].replace(" ", "").replace(",", "").replace("\\xa", ""))[0][0]
    currency_symbol = ''.join([i for i in unfetched_price if not i.isdigit()]).replace('Â', '').strip()
    
    return {
        'price': price,
        'currency_symbol': currency_symbol,
        'is_available': is_available
    }