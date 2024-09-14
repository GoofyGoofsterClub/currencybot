def get_cur_exchange_rate(cur1, cur2):
    r = requests.get('https://duckduckgo.com/js/spice/currency/1/{}/{}'.format(cur1, cur2))

    if (r.status_code != 200):
        return False

    try:
        unwrapped_response = r.text[r.text.find('\n') + 1 : r.text.rfind('\n') - 2]
        json_response = json.loads(unwrapped_response)
        value = json_response['to'][0]['mid']
    except:
        return False
    return value
