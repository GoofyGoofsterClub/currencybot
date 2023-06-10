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
    print(currency)
    for c in currencies:
        print("FIND_CURRENCY: POINT OF FAILURE 1")
        if c['cc'] == currency or currency in c['aliases']:
            print("FIND_CURRENCY: POINT OF FAILURE 2")
            return c
        elif currency.startswith(c['symbol']):
            print("FIND_CURRENCY: POINT OF FAILURE 3")
            currency = currency.replace(c['cc'], '')
            print("FIND_CURRENCY: POINT OF FAILURE 4")
            if currency.isnumeric():
                print("FIND_CURRENCY: POINT OF FAILURE 5")
                return c
    print("END OF FIND_CURRENCY")
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
                if not amount.isnumeric() and amount < 0:
                    continue
                currency = find_currency(word.lower())
                converted = api.get_exchange_rates(
                    base_currency=currency['cc'],
                    start_date=yesterday,
                    end_date=today,
                    targets=[os.getenv("DEFAULT_CURRENCY")]
                )
                converted = converted[yesterday][os.getenv("DEFAULT_CURRENCY")] * float(amount)
                converted = converted.__round__(2)
                message_to_send.append(f'{amount} {currency["cc"].upper()} is {converted} {os.getenv("DEFAULT_CURRENCY")}')
        
        if len(message_to_send) > 0:
            await message.reply('\n'.join(message_to_send))
            
intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(os.getenv('DISORD_TOKEN'))
