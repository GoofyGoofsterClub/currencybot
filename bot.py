import discord
import os
import json
import string
from easy_exchange_rates import API
from datetime import datetime, timedelta

currencyapi = api = API()

with open('currencies.json') as f:
    currencies = json.load(f)

def find_currency(currency):
    for c in currencies:
        if c['cc'] == currency or currency in c['aliases']:
            return c
        elif currency.startswith(c['symbol']) and currency.replace(c['symbol'], '').isnumeric():
            currency = currency.replace(c['symbol'], '')
            if currency.isnumeric():
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
            if find_currency(word.lower()):
                print("FOUND CURRENCY: " + word)
                yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
                today = datetime.strftime(datetime.now(), '%Y-%m-%d')
                amount = message.content.split()[message.content.split().index(word) - 1]
                amount = ''.join([i for i in amount if i.isnumeric()])


                currency = find_currency(word.lower())
                if word.startswith(currency['symbol']):
                    amount = word.replace(currency['symbol'], '')
                    if amount.isnumeric():
                        amount = float(amount)

                rates = api.get_exchange_rates(
                    base_currency=currency['cc'],
                    start_date=yesterday,
                    end_date=today,
                    targets=os.getenv("DEFAULT_CURRENCY").split(',')
                )
                print(rates)
                messageout = (f'{amount} {currency["cc"].upper()} is ')      
                for rate in rates[yesterday]:
                    print(rate)
                    messageout += (f'{(rates[yesterday][rate] * float(amount)).__round__(2)} {rate} ')
                    #print(rate, rates[yesterday][rate])
                    print(f'{(rates[yesterday][rate] * float(amount)).__round__(2)} {rate} ')
                message_to_send.append(messageout)
        
        if len(message_to_send) > 0:
            await message.reply('\n'.join(message_to_send))
            
intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(os.getenv('DISORD_TOKEN'))
