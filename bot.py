import discord
import json
import re
from datetime import datetime, timedelta
from utility.convert import get_cur_exchange_rate
from utility.text import find_currency, does_text_contain_currency, find_command_in_alias
from utility.misc import shit_broke
from utility.statics import CURRENCYREGEX, ENVRATE, ENVPREFIX, ENVTOKEN
# Commands
from commands.convert import convert as command_convert
from commands.math import math as command_math
from commands.date import date as command_date

COMMANDS = {
    "convert": {
        "run": command_convert,
        "alias": ["cc"]
    },
    "math": {
        "run": command_math,
        "alias": ["m"]
    },
    "date": {
        "run": command_date,
        "alias": ["d"]
    }
}

with open('currencies.json') as f:
    currencies = json.load(f)

_globals = {
    "ENVRATE": ENVRATE,
    "currencies": currencies
}

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

        # Commands
        if message.content.startswith(ENVPREFIX):
            print(' (command)', end='')
            command = message.content.split()[0][1:]
            args = message.content.split()[1:]
            
            # Checking in dictionary of commands and running the function specified
            if command in COMMANDS:
                return await COMMANDS[command]['run'](message, args, _globals)
            
            # Checking for aliases
            alias_test = find_command_in_alias(command, COMMANDS)
            if alias_test:
                return await COMMANDS[alias_test]['run'](message, args, _globals)

            return

        # In-text conversion

        matches = re.finditer(CURRENCYREGEX, message.content, re.MULTILINE)
        print('')

        currency_data = []

        for matchNum, match in enumerate(matches, start=1):
            amount_unwrapped = float(match.group(1))
            amount_k = len(match.group(2)) if match.group(2) else 0
            currency = find_currency(match.group(4), currencies)

            currencies_to_compare = ENVRATE.copy()
            exchange_rates = []

            if (amount_k > 0):
                amount_unwrapped = amount_unwrapped * (1000 ** amount_k)

            print(amount_unwrapped)

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
