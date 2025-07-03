import requests
import re

def get_vqd(query):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0',
    }

    params = {
        'q': query,
    }

    response = requests.get('https://duckduckgo.com/', params=params, headers=headers)

    # Extract vqd using regex
    match = re.search(r'vqd=([\d-]+)&', response.text)
    if match:
        return match.group(1)

    # Alternative pattern if vqd is embedded differently
    match = re.search(r"vqd='([\d-]+)'", response.text)
    if match:
        return match.group(1)

    raise Exception('Could not extract vqd token')