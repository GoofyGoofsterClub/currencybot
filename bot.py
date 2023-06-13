import discord
import os
import json
import string
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
    for c in currencies:
        alias_re = "^\d+[\.\,]?\d*" + '|'.join(c["aliases"]) + "$"
        if c['cc'] == currency or currency in c['aliases']:
            return c
        elif currency.startswith(c['symbol']):
            currency = currency.replace(c['symbol'], '')
            if currency.replace('k', '').isnumeric():
                return c
        elif currency.endswith(c['cc']):
            return c
        elif c['aliases'] and re.search(alias_re, currency):
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
        
        message.content = re.sub(r'\<\:?\@?\w+(\:\d+)?\>', '', message.content).lower()

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

<<<<<<< HEAD
        matches = re.finditer(CURRENCYREGEX, message.content, re.MULTILINE)
        if not matches:
            print()
            return
=======
        msg_sep = message.content.split()
        currency_found = []
        for word in msg_sep:
            word = word.translate(str.maketrans('', '', string.punctuation.replace('$', '')))
            currency = find_currency(word.lower())
            if currency:
                currency_found.append(currency)
                yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
                today = datetime.strftime(datetime.now(), '%Y-%m-%d')

                if re.search("\d+[\.\,]?\d*k$", msg_sep[msg_sep.index(word) - 1]):
                    #thousands match
                    amount = msg_sep[msg_sep.index(word) - 1]
                    amount = ''.join([i for i in amount if (i.isnumeric() or i == ',' or i == '.')]).replace(',', '.')
                    amount = float(amount)*1000
                elif re.search("\d+[\.\,]?\d*", msg_sep[msg_sep.index(word) - 1]):
                    #previous word match
                    amount = msg_sep[msg_sep.index(word) - 1]
                    amount = ''.join([i for i in amount if (i.isnumeric() or i == ',' or i == '.')]).replace(',', '.')
                elif re.search("\d+[\.\,]?\d*k$", word):
                    #current thousands match
                    amount = ''.join([i for i in word if (i.isnumeric() or i == ',' or i == '.')]).replace(',', '.')
                    amount = float(amount)*1000
                elif re.search("\d+[\.\,]?\d*", word):
                    #current word match
                    amount = ''.join([i for i in word if (i.isnumeric() or i == ',' or i == '.')]).replace(',', '.')

                try:
                    amount = float(amount)
                except:
                    print(f' (error: {amount} is not a float)')
                    break

                TEMPENVRATE = ENVRATE.copy()
                try:
                    TEMPENVRATE.pop(ENVRATE.index(currency['cc'].upper()))
                except:
                    pass

                rates = api.get_exchange_rates(
                    base_currency=currency['cc'],
                    start_date=yesterday,
                    end_date=today,
                    targets=TEMPENVRATE
                )
                messageout = (f'{amount} {currency["cc"].upper()} is ')   
                for i, rate in enumerate(rates[yesterday]):
                    result = (rates[yesterday][rate] * amount).__round__(2)
                    if result > 9999:
                        result = result/1000
                        messageout += (f'{result.__round__(2)}k {rate} ')
                    else:
                        messageout += (f'{result} {rate} ')
                    if i != len(rates[yesterday]) - 1:
                        messageout += "or "
                message_to_send.append(messageout)
                
        print(f' ({len(currency_found)} currencies found: {", ".join([c["cc"] for c in currency_found])})', end='')
        if len(message_to_send) > 0:
            await message.reply('\n'.join(message_to_send))
>>>>>>> bcbf166a6cbe7fe6dae2b824586628fca69d1ff2
        
        yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
        today = datetime.strftime(datetime.now(), '%Y-%m-%d')

        currency_data = []
        for matchNum, match in enumerate(matches, start=1):
            this_rate = ""
            amount_unwrapped = float(match.group(1))
            amount_k = len(match.group(2)) if match.group(2) else 0
            currency = find_currency(match.group(3))
            if not currency:
                currency = find_currency(match.group(2) + match.group(3))
                if not currency:
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
                "amount": amount,
                "currency": currency,
                "rates": matched_rates
            })

            print(f" ({amount} {currency})", end='')

        if len(currency_data) == 0:
            return
        data = [{'amount': 1200.0, 'currency': 'JPY', 'rates': {'RUB': 720.56, 'SEK': 93.02}}]

        message_to_send = f"### Conversion rates for this message\n\n" + \
            '\n'.join([f"* {data['amount']} {data['currency']} is ~({' or '.join([f'__{value}__ {key}' for key, value in data['rates'].items()])})" for data in currency_data])
        
        await message.reply(message_to_send)

      
        print('')
            
intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(ENVTOKEN)
