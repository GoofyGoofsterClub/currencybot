import requests
from utility.ddg import get_vqd

def get_stock_info(ticker):
    cookies = {
        'dcm': '3',
    }
    query = f"${ticker}"
    vqd = get_vqd(query)

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://duckduckgo.com/',
        'X-Requested-With': 'XMLHttpRequest',
        'DNT': '1',
        'Sec-GPC': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
    }
    response = requests.get(
        f"https://duckduckgo.com/stocks.js?action=quote&symbol={ticker}&query=${ticker}&vqd={vqd}",
        cookies=cookies,
        headers=headers,
    ).json()

    return response

async def stock(message, args, _globals):
    if len(args) >= 1:
        try:
            st = get_stock_info(args[0])

            if 'code' in st:
                await message.reply(f"An error occurred while processing this request. ({st['code']})")
                return False
            
            st_info = {
                "name": st['companyName'],
                "ticker": st['symbol'],
                "change": st['change'],
                "change_pr": round(st['changePercent'] * 100, 2),
                "change_good": '<:arrowup:1386044488144916752>' if st['changePercent'] >= 0 else '<:arrowdown:1386044531039928452>',
                "price": st['latestPrice'],
                "currency": st['currency'],
                "exchange": st['primaryExchange']
            }

            await message.reply(f"{st_info['name']} ({st_info['ticker']})'s stock is worth **{st_info['price']} {st_info['currency']}** as of now on {st_info['exchange']} with {st_info['change_good']} $`{st_info['change_pr']}`% 24-hour change.")
        except Exception as e:
            await message.reply(f"An error occurred while processing this request. ({e})")
    else:
        await message.reply('Invalid arguments')