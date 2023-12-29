import re
import requests
import time
import json

pattern = r'https:\/\/www\.amazon\.((\w+)(\.\w+)?)\/(.*)/dp/(\w+)'
swatch_pattern = r'<spanclass=\"a-size-minitwisterSwatchPrice\">(.*)(<\/span><\/span>)'

def regex(url):
    if re.match(pattern, url):
        regex_match = list(re.findall(pattern, url))[0]
        return {
            "domain": "amazon.{}".format(regex_match[0]),
            "asin": regex_match[4]
        }
    return False

def get_pricing_info(domain, asin):
    request_data = requests.post("https://{2}/gp/twister/dimension?isDimensionSlotsAjax=1&asinList={0}&vs=1&productTypeDefinition=INTERNAL_MEMORY&productGroupId=ce_display_on_website&parentAsin={0}&isPrime=0&qid={1}&sr=8-1&isOneClickEnabled=0&originalHttpReferer=https://amazon.com&keywords=&landingAsin={0}&deviceType=web&showFancyPrice=true&twisterFlavor=twisterPlusDesktopConfigurator".format(asin, round(time.time()), domain))
    json_data = json.loads(request_data.text)
    price = json_data['Value']['content']['twisterSlotJson']['price']
    is_available = json_data['Value']['content']['twisterSlotJson']['isAvailable']
    
    unfetched_price = re.findall(swatch_pattern,
                                 json_data['Value']['content']['twisterSlotDiv'].replace(" ", "").replace(",", "").replace("\\xa", ""))[0][0]
    currency_symbol = ''.join([i for i in unfetched_price if not i.isdigit()])
    
    return {
        'price': price,
        'currency_symbol': re.compile(r'[^a-zA-Z\.]+').sub('', currency_symbol),
        'is_available': is_available
    }