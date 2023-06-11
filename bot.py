import discord
import os
import json
import string
import re
from easy_exchange_rates import API
from datetime import datetime, timedelta

currencyapi = api = API()

with open('currencies.json') as f:
    currencies = json.load(f)

def find_currency(currency):
    for c in currencies:
        alias_re = "^\d+[\.\,]?\d*" + '|'.join(c["aliases"]) + "$"
        if c['cc'] == currency or currency in c['aliases']:
            return c
        elif currency.startswith(c['symbol']):
            currency = currency.replace(c['symbol'], '')
            if currency.isnumeric():
                return c
        elif currency.endswith(c['cc']):
            return c
        elif re.search(alias_re, currency):
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
        
        if message.content.startswith(os.getenv('BOT_PREFIX')):
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
        message_to_send = []
        if message.author == self.user:
            return
        
        for word in message.content.split():
            word = word.translate(str.maketrans('', '', string.punctuation.replace('$', '')))
            currency = find_currency(word.lower())
            if currency:
                #yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
                today = datetime.strftime(datetime.now(), '%Y-%m-%d')
                amount = message.content.split()[message.content.split().index(word) - 1]
                amount = ''.join([i for i in amount if i.isnumeric() or i == ',' or i == '.']).replace(',', '.')
                if not amount:
                    amount = message.content.split()[message.content.split().index(word)]
                    amount = ''.join([i for i in amount if i.isnumeric() or i == ',' or i == '.']).replace(',', '.')

                try:
                    amount= float(amount)
                except:
                    print(f'{amount} is not a float')
                    break

                if word.startswith(currency['symbol']):
                    amount = word.replace(currency['symbol'], '')
                    if amount.isnumeric():
                        amount = float(amount)

                envrate = os.getenv("DEFAULT_CURRENCY").split(',')
                try:
                    envrate.pop(envrate.index(currency['cc'].upper()))
                except:
                    continue

                rates = api.get_exchange_rates(
                    base_currency=currency['cc'],
                    start_date=today,
                    end_date=today,
                    targets=envrate
                )

                messageout = (f'{amount} {currency["cc"].upper()} is ')

                for i, rate in enumerate(rates[today]):
                    messageout += (f'{(rates[today][rate] * float(amount)).__round__(2)} {rate} ')
                    if i != len(rates[today]) - 1:
                        messageout += "or "
                    
                message_to_send.append(messageout)
        
        if len(message_to_send) > 0:
            await message.reply('\n'.join(message_to_send))
            
intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(os.getenv('DISORD_TOKEN'))
