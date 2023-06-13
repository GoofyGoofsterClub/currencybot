import discord
import os
import json
import re
from easy_exchange_rates import API
from datetime import datetime, timedelta

currencyapi = api = API()

ENVRATE = os.getenv("DEFAULT_CURRENCY").split(',')
ENVTOKEN = os.getenv('DISORD_TOKEN')
ENVPREFIX = os.getenv('BOT_PREFIX')
CURRENCYREGEX = r"(\d+\.?\d*)(k*)? ?(\w+)"

with open('currencies.json') as f:
    currencies = json.load(f)

def find_currency(currency):
    if not currency.strip():
        return None
    
    print(f"'{currency}'")

    for c in currencies:
        alias_re = "^\d+[\.\,]?\d*" + '|'.join(c["aliases"])
        if c['cc'] == currency or currency in c['aliases']:
            print(f"Found currency: {c['cc']} - Trigger 1")
            return c
        elif currency.startswith(c['symbol']):
            print(f"Found currency: {c['cc']} - Trigger 2")
            currency = currency.replace(c['symbol'], '')
            if currency.replace('k', '').isnumeric():
                print(f"Found currency: {c['cc']} - Trigger 3")
                return c
        elif currency.endswith(c['cc']):
            print(f"Found currency: {c['cc']} - Trigger 4")
            return c
        elif c['aliases'] and re.search(alias_re, currency):
            print(f"Found currency: {c['cc']} - Trigger 5")
            return c
    return None

def does_text_contain_currency(text):
    for c in currencies:
        if c['cc'] in text:
            return c
    return False

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        
        if message.author == self.user:
            return
        
        message.content = re.sub(r'\<(a\:)?\:?\@?\w+(\:\d+)?\>', '', message.content).lower()

        print(f"{message.author}: {message.content}", end='')

        if message.content.startswith(ENVPREFIX):
            print(' (command)', end='')
            command = message.content.split()[0][1:]
            if command == "convert":
                args = message.content.split()[1:]
                yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
                today = datetime.strftime(datetime.now(), '%Y-%m-%d')
                if len(args) == 3:
                    amount = args[0]
                    currency = args[1]
                    to_currency = args[2]
                    converted = api.get_exchange_rates(
                        base_currency=currency,
                        start_date=yesterday,
                        end_date=today,
                        targets=[currency, to_currency]
                    )
                    converted = converted[yesterday][to_currency.upper()] * float(amount)
                    converted = converted.__round__(2)
                    await message.reply(f'{amount} {currency.upper()} is ~{converted} {to_currency.upper()}.')
                else:
                    await message.reply('Invalid arguments')
            return

        matches = re.finditer(CURRENCYREGEX, message.content, re.MULTILINE)
        if not matches:
            print()
            return
        
        yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
        today = datetime.strftime(datetime.now(), '%Y-%m-%d')

        currency_data = []
        for matchNum, match in enumerate(matches, start=1):
            amount_unwrapped = float(match.group(1))
            amount_k = len(match.group(2)) if match.group(2) else 0
            currency = find_currency(match.group(3))
            if currency == None:
                currency = find_currency(match.group(2) + match.group(3))
                if currency == None:
                    continue
                else:
                    amount_k = 0
            currency = currency['cc'].upper()
            amount = amount_unwrapped * (1000 ** amount_k)
            
            rates = api.get_exchange_rates(
                base_currency=currency,
                start_date=yesterday,
                end_date=today,
                targets=ENVRATE
            )
            
            matched_rates = {}
            for rate in rates[yesterday]:
                if rate != currency:
                    matched_rates[rate] = (rates[yesterday][rate] * amount).__round__(2)

            currency_data.append({
                "amount": f'{amount:,}',
                "currency": currency,
                "rates": matched_rates
            })

            print(f" ({amount} {currency})", end='')

        if len(currency_data) == 0:
            return

        message_to_send = f"### <a:DinkDonk:956632861899886702> {len(currency_data)} money mention{'s' if len(currency_data) > 1 else ''} detected\n\n" + \
            '\n'.join([f"* **{data['amount']} {data['currency']}** is {' or '.join([f'*{value:,} {key}*' for key, value in data['rates'].items()])}" for data in currency_data])
        
        await message.reply(message_to_send)

      
        print('')
            
intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(ENVTOKEN)
