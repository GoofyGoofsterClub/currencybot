import discord
import os
import requests
import json
import re
from datetime import datetime, timedelta
from utility.convert import get_cur_exchange_rate
from utility.text import find_currency, does_text_contain_currency

ENVRATE = os.getenv("DEFAULT_CURRENCY").split(',')
ENVTOKEN = os.getenv('DISCORD_TOKEN')
ENVPREFIX = os.getenv('BOT_PREFIX')
CURRENCYREGEX = r"(\d+\.?\d*)(k*)? ?(\w+)"

with open('currencies.json') as f:
    currencies = json.load(f)

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

        # This regex removes emotes from the message, so it doesnt pick up random emotes as currency / value.
        message.content = re.sub(r'\<(a\:)?\:?\@?\w+(\:\d+)?\>', '', message.content).lower()

        # Log out the message for better debugging
        print(f"{message.author}: {message.content}", end='')

        if message.content.startswith(ENVPREFIX):
            print(' (command)', end='')
            command = message.content.split()[0][1:]
            if command == "convert":
                args = message.content.split()[1:]
                if len(args) == 3:
                    amount = args[0]
                    currency = find_currency(args[1], currencies)
                    to_currency = find_currency(args[2], currencies)

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

        currency_data = []

        for matchNum, match in enumerate(matches, start=1):
            amount_unwrapped = float(match.group(1))
            amount_k = len(match.group(2)) if match.group(2) else 0
            currency = find_currency(match.group(3), currencies)

            currencies_to_compare = ENVRATE.copy()
            exchange_rates = []

            if (amount_k > 0):
                amount_unwrapped = amount_unwrapped * (1000 ** amount_k)

            if (amount_unwrapped == 0):
                continue
            
            try:
                for defaultCurrency in currencies_to_compare:
                    currency_obj = find_currency(defaultCurrency, currencies)
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
