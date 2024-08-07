import discord
import os
import requests
import json
import re
from datetime import datetime, timedelta
import api_modules.amazon

ENVRATE = os.getenv("DEFAULT_CURRENCY").split(',')
ENVTOKEN = os.getenv('DISORD_TOKEN')
ENVPREFIX = os.getenv('BOT_PREFIX')
CURRENCYREGEX = r"(\d+\.?\d*)(k*)? ?(\w+)"

with open('currencies.json') as f:
    currencies = json.load(f)

def find_currency(currency):
    if not currency.strip():
        return None
    
    currency = currency.lower()

    for c in currencies:
        if c['cc'] == currency:
            return c
        if any([re.match(alias, currency) for alias in c['aliases']]):
            return c
    return None

def does_text_contain_currency(text):
    for c in currencies:
        if c['cc'] in text:
            return c
    return False

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

async def shit_broke(message):
    await message.reply("Shit broke. You're either brainded or blame [DuckDuckGo](https://duckduckgo.com).")
    return True

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        
        if message.author == self.user:
            return
        
        original_content = message.content
        message.content = re.sub(r'\<(a\:)?\:?\@?\w+(\:\d+)?\>', '', message.content).lower()

        print(f"{message.author}: {message.content}", end='')

        if message.content.startswith(ENVPREFIX):
            print(' (command)', end='')
            command = message.content.split()[0][1:]
            if command == "convert":
                args = message.content.split()[1:]
                if len(args) == 3:
                    amount = args[0]
                    currency = find_currency(args[1])
                    to_currency = find_currency(args[2])

                    if currency == None or to_currency == None:
                        await message.reply("Please check the currency specified.")
                        return

                    converted = get_cur_exchange_rate(
                        currency['cc'],
                        to_currency['cc']
                    )
                    if (not converted):
                        await shit_broke(message)
                        return

                    total_value = float(amount) * float(converted)
                    await message.reply(f'{amount} {currency["cc"].upper()} is ~{round(total_value, 3)} {to_currency["cc"].upper()}.')
                else:
                    await message.reply('Invalid arguments')
            return

        matches = re.finditer(CURRENCYREGEX, message.content, re.MULTILINE)
        print('')

        amazon_url = api_modules.amazon.regex(original_content)


        if type(amazon_url) == list and len(amazon_url) > 0:
            amazon_data = []

            for data in amazon_url:
                if data['domain'] == 'amazon.cn':
                    continue

                try:
                    result = api_modules.amazon.get_pricing_info(data['domain'], data['asin'])
                    result['product_name'] = data['product_name']
                    amazon_data.append(result)
                except Exception as e:
                    continue
            
            if(len(amazon_data) > 0):
                response_text = "### <a:DinkDonk:956632861899886702> {} amazon link(s) found.\n".format(len(amazon_data))

                for k, v in enumerate(amazon_data):
                    try:
                        if v['currency_symbol']:
                            v['currency_symbol'] = v['currency_symbol'].replace('.', '').strip()
                            if (v['currency_symbol'] == '$'): v['currency_symbol'] = 'usd'
                            currency_data = find_currency(v['currency_symbol'])

                            actual_price = '{} {}'.format(v['price'], currency_data['cc'].upper())
                            
                            converted_prices = []

                            currencies_to_compare = ENVRATE.copy()

                            for defaultCurrency in currencies_to_compare:
                                currency_obj = find_currency(defaultCurrency)
                                if currency_obj == currency_data:
                                    continue
                                converted_prices.append('{} {}'.format(
                                    round(float(get_cur_exchange_rate(currency_data['cc'], currency_obj['cc'])) * float(v['price']), 3),
                                    currency_obj['cc'].upper()
                                ))

                            converted_price = ', '.join(converted_prices)
                        else:
                            actual_price = v['unfetched_price_text']
                            converted_price = '???'

                        response_text += '{}. {} [{}](<{}>) is **{}** **({})**\n'.format(
                            k + 1,
                            '❓' if v['is_available'] == None else '✅' if v['is_available'] else '�',
                            v['product_name'],
                            v['url'],
                            actual_price,
                            converted_price
                        )
                    except Exception as e:
                        continue

                await message.reply(response_text)
        currency_data = []

        for matchNum, match in enumerate(matches, start=1):
            amount_unwrapped = float(match.group(1))
            amount_k = len(match.group(2)) if match.group(2) else 0
            currency = find_currency(match.group(3))

            currencies_to_compare = ENVRATE.copy()
            exchange_rates = []

            if (amount_k > 0):
                amount_unwrapped = amount_unwrapped * (1000 ** amount_k)

            if (amount_unwrapped == 0):
                continue
            
            try:
                for defaultCurrency in currencies_to_compare:
                    currency_obj = find_currency(defaultCurrency)
                    if currency == currency_obj:
                        continue
                    exchange_rates.append('**{} {}**'.format(
                        round(amount_unwrapped * get_cur_exchange_rate(currency['cc'], defaultCurrency), 3),
                        currency_obj['cc'].upper()
                    ))

            except:
                continue
            if (not exchange_rates):
                await shit_broke(message)
                return

            currency_data.append('{} **{}** is {}'.format(
                amount_unwrapped,
                currency['cc'].upper(),
                ', '.join(exchange_rates)
            ))

        if (len(currency_data) < 1):
            return
        
        response_text = "### <a:DinkDonk:956632861899886702> {} currency mentions found.\n".format(len(currency_data))

        for k, v in enumerate(currency_data):
            response_text += '{}. {}\n'.format(k+1, v)

        n = 1900
        responses = [response_text[i:i+n] for i in range(0, len(response_text), n)]

        for response in responses:
            await message.reply(response)

            
intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(ENVTOKEN)
