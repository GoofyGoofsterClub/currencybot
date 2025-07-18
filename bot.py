import asyncio
import discord
import json
import re
import time
import importlib
import os
import pymongo

from datetime import datetime
from discord.ext import tasks
from glob import glob

from utility.convert import get_cur_exchange_rate
from utility.text import find_currency, find_command_in_alias
from utility.misc import shit_broke
from utility.statics import CURRENCYREGEX, ENVRATE, ENVPREFIX, ENVTOKEN
from utility.crypto import get_crypto_rate

from commands.convert import convert as command_convert
from commands.math import math as command_math
from commands.date import date as command_date
from commands.betastock import stock as command_beta_stock
from commands.remind import remind as command_remind
from commands.reminders import reminders as command_reminders
from commands.unremind import unremind as command_unremind
from commands.set import _set as command_set
from commands.whois import _whois as command_whois


COMMANDS = {
    "convert": {"run": command_convert, "alias": ["cc"]},
    "math": {"run": command_math, "alias": ["m"]},
    "date": {"run": command_date, "alias": ["d"]},
    "stock": {"run": command_beta_stock, "alias": ["st"]},
    "remind": {"run": command_remind, "alias": ["r"]},
    "reminders": {"run": command_reminders, "alias": ["rs"]},
    "unremind": {"run": command_unremind, "alias": ["ur"]},
    "set": {"run": command_set, "alias": []},
    "whois": {"run": command_whois, "alias": ["rdap"]},
}

for _, command in enumerate(COMMANDS):
    print(f"{_} :: Registering command {command}")

with open("currencies.json") as f:
    currencies = json.load(f)

with open("custom.json") as f:
    custom_currencies = json.load(f)

MODULES = []
MODULE_REGEX = {}

for idx, file_path in enumerate(glob("./api_modules/**/*.py", recursive=True)):
    module_name = file_path[2:-3].replace("/", ".")
    print(f"{idx} :: Loading module {module_name}...")
    module = importlib.import_module(module_name)
    MODULES.append(module)
    MODULE_REGEX[module.LINK_REGEX] = module.parse_price

print(f"Loaded {len(MODULES)} API module(s)...")

MONGO_URI = (
    f"mongodb://"
    f"{os.environ['MONGO_HOST']}:{os.environ['MONGO_PORT']}/"
    f"?authSource={os.environ['MONGO_DB']}"
)

print(f"Connecting mongodb to {MONGO_URI}")

dbclient = pymongo.MongoClient(MONGO_URI)
currdb = dbclient['curr']
_globals = {"ENVRATE": ENVRATE, "currencies": currencies, 'currdb': currdb}

def get_due_reminders():
    now = int(time.time()) 
    return list(currdb['reminders'].find({'timestamp': {'$lte': now}}))

def remove_reminder_by_id(reminder_id):
    return currdb['reminders'].delete_one({'_id': reminder_id})

@tasks.loop(seconds=1.0)
async def reminder_check():
    try:
        reminders = await asyncio.to_thread(get_due_reminders)
        for reminder in reminders:
            channel = client.get_channel(reminder['channel_id'])
            await channel.send(f"<@{reminder['remindee_id']}> <a:dinkDonk:989155125673214032> `{reminder['reminder_text']}`")
            await asyncio.to_thread(remove_reminder_by_id, reminder['_id'])
    except Exception as e:
        print(e)

@reminder_check.before_loop
async def before_reminder_check():
    await client.wait_until_ready()

@tasks.loop(seconds=60.0)
async def watchdog():
    if not reminder_check.is_running():
        reminder_check.start()

class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")
        if not reminder_check.is_running():
            reminder_check.start()
        if not watchdog.is_running():
            watchdog.start()
    
    async def on_resumed(self):
        print(f"Resumed connection to {self.user}")
        if not reminder_check.is_running():
            reminder_check.start()
        if not watchdog.is_running():
            watchdog.start()

    async def on_message(self, message):
        if message.author == self.user:
            return

        original_content = message.content
        message.content = re.sub(
            r"\<a?:\w+:\d+\>", "", original_content
        ).lower()
        print(f"{message.author}: {message.content}", end="")

        if message.content.startswith(ENVPREFIX):
            print(" (command)", end="")
            parts = message.content.split()
            command_name = parts[0][1:]
            args = parts[1:]

            command_func = COMMANDS.get(command_name)
            if not command_func:
                command_name = find_command_in_alias(command_name, COMMANDS)
                command_func = COMMANDS.get(command_name)

            if command_func:
                return await command_func["run"](message, args, _globals)
            return

        print("")
        currency_data_list = []
        link_results = []

        for match in re.finditer(CURRENCYREGEX, message.content, re.MULTILINE):
            amount = float(match.group(1))
            magnitude = len(match.group(2)) if match.group(2) else 0
            currency_code = match.group(4)

            if magnitude > 0:
                amount *= 1000**magnitude

            if amount == 0:
                continue

            current_currency = find_currency(currency_code, currencies)
            is_custom_currency = False
            is_crypto_currency = False

            if not current_currency:
                current_currency = find_currency(currency_code, custom_currencies)
                is_custom_currency = bool(current_currency)

            if not current_currency:
                if currency_code.startswith("$"):
                    currency_code = currency_code[1:]
                    current_currency = get_crypto_rate(currency_code)
                    is_crypto_currency = bool(current_currency)

            if not current_currency:
                continue

            print(current_currency)

            exchange_rates_info = []
            try:
                for target_code in ENVRATE:
                    target_currency = find_currency(target_code, currencies)
                    if current_currency == target_currency:
                        continue

                    if is_custom_currency:
                        from_unit = current_currency["unit"]["conversion_unit"]
                        converted_amount = (
                            amount
                            * current_currency["unit"]["conversion_amount"]
                            * get_cur_exchange_rate(from_unit, target_code)
                        )
                    elif is_crypto_currency:
                        converted_amount = float(amount) * current_currency['price'] * get_cur_exchange_rate('USD', target_code)
                    else:
                        converted_amount = amount * get_cur_exchange_rate(
                            current_currency["cc"], target_code
                        )

                    exchange_rates_info.append(
                        f"**{round(converted_amount, 3)} {target_currency['cc'].upper()}**"
                    )
            except Exception as e:
                raise e
                continue
            print(exchange_rates_info)
            if exchange_rates_info:
                currency_data_list.append(
                    f"{amount} **{current_currency['cc'].upper()}** is "
                    f"{', '.join(exchange_rates_info)}"
                )
            else:
                await shit_broke(message)
                return

        for pattern, parser in MODULE_REGEX.items():
            for match in re.finditer(pattern, message.content):
                try:
                    link_results.append(parser(match[0]))
                except Exception:
                    pass

        if not currency_data_list and not link_results:
            return

        response_parts = []

        if currency_data_list:
            response_parts.append(
                f"### <a:DinkDonk:956632861899886702> {len(currency_data_list)} "
                "currency mentions found."
            )
            for idx, line in enumerate(currency_data_list, 1):
                response_parts.append(f"{idx}. {line}")

        if link_results:
            response_parts.append(
                f"\n### <a:DinkDonk:956632861899886702> {len(link_results)} links found."
            )
            for idx, result in enumerate(link_results, 1):
                curr_info = find_currency(result["currency"], currencies)
                base_price = result["price"]
                exchange_info = []

                for target_code in ENVRATE:
                    target_currency = find_currency(target_code, currencies)
                    if curr_info == target_currency:
                        continue
                    converted = round(
                        base_price
                        * get_cur_exchange_rate(curr_info["cc"], target_code),
                        3,
                    )
                    exchange_info.append(
                        f"**{converted} {target_currency['cc'].upper()}**"
                    )

                response_parts.append(
                    f"{idx}. [{result['name']}]({result['link']}) is "
                    f"**{base_price} {curr_info['cc'].upper()}** or "
                    f"{', '.join(exchange_info)}"
                )

        response_text = "\n".join(response_parts)
        for chunk in [response_text[i : i + 1900] for i in range(0, len(response_text), 1900)]:
            await message.reply(chunk)

    async def on_reaction_add(self, reaction: discord.Reaction, user):
        if not user.bot and reaction.message.author == self.user:
            if reaction.emoji == "❌":
                reminder_db = await asyncio.to_thread(currdb["reminders"].find_one, {"message_id": reaction.message.id})
                if reminder_db:
                    if user.id == reminder_db["remindee_id"] or user.id == reminder_db["creator_id"]:
                        await reaction.message.delete()
                        await asyncio.to_thread(currdb["reminders"].delete_one, {"message_id": reaction.message.id})
                        await reaction.message.channel.send(f"<@{user.id}>, reminder for <@{reminder_db['remindee_id']}> has been deleted. \n\n-# Reminder ID: `{reminder_db['reminder_id']}`")

intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(ENVTOKEN)