import random
import string
import re
import asyncio
import dateparser
from datetime import datetime
from zoneinfo import ZoneInfo

async def remind(message, args, _globals):

    if not args:
        await message.reply(f"Usage: $remind <who> <what> <when>")
        return None

    remindee_id = None
    target_arg = args[0].lower()

    if target_arg == "me":
        remindee_id = message.author.id
        args.pop(0) 
    else:
        mention_match = re.match(r"<@!?(\d+)>", target_arg)
        if mention_match:
            remindee_id = int(mention_match.group(1))
            args.pop(0)
        else:
            remindee_id = message.author.id

    if not args:
        await message.reply("Please specify when to be reminded.")
        return None

    time_keywords = ["in", "on", "at"]
    time_string_index = -1

    for i, arg in enumerate(args):
        if arg.lower() in time_keywords:
            time_string_index = i
            break

    if time_string_index == -1:
        await message.reply("Error: Could not parse time. Use 'in', 'at', or 'on'.")
        return None

    reminder_text_list = args[:time_string_index]
    time_string = " ".join(args[time_string_index:])

    if reminder_text_list and reminder_text_list[0].lower() == "about":
        reminder_text_list.pop(0)

    reminder_text = " ".join(reminder_text_list)
    if not reminder_text:
        reminder_text = "Here's your reminder!"

    
    timeMatch = re.search(r"<t:(\d+)(?::[[:alpha:]]?)?>",time_string)

    if timeMatch != None:
        reminder_datetime = datetime.fromtimestamp(int(timeMatch.group(1)),tz=ZoneInfo("Etc/UTC"))

    else:
        settings = {
            'PREFER_DATES_FROM': 'future',
            'RETURN_AS_TIMEZONE_AWARE': True,
            'TIMEZONE': 'Europe/Stockholm'
        }

        timezone = await asyncio.to_thread(_globals['currdb']['user_preferences'].find_one, {"user_id": message.author.id}, {"timezone": 1})
        if timezone:
            settings['TIMEZONE'] = timezone['timezone']

        reminder_datetime = dateparser.parse(time_string, settings=settings)

    if reminder_datetime is None:
        await message.reply(f"Error: Could not understand time '{time_string}'")
        return None

    now_utc = datetime.now(reminder_datetime.tzinfo)
    if reminder_datetime < now_utc:
        await message.reply("Error: Cannot set a reminder in the past.")
        return None

    timestamp = int(reminder_datetime.timestamp())

    reminder_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))

    reminder_data = {
        "reminder_id": reminder_id,
        "creator_id": message.author.id,
        "remindee_id": remindee_id,
        "reminder_text": reminder_text,
        "timestamp": timestamp,
        "channel_id": message.channel.id,
        "message_id": message.id
    }

    
    try:
        reminder = await asyncio.to_thread(_globals['currdb']['reminders'].insert_one, reminder_data)
    except Exception as e:
        await message.reply(f"An error occurred while processing this request. ({e})")
        return

    confirmation_text = (
        f"Reminder set for <@{remindee_id}> about \"{reminder_text}\" "
        f"at <t:{timestamp}:F>.\n\n"
        f"-# Reminder ID: `{reminder_id}`"
    )
    
    msg = await message.reply(confirmation_text)

    try:
        await asyncio.to_thread(_globals['currdb']['reminders'].update_one, {"reminder_id": reminder_id}, {"$set": {"message_id": msg.id}})
        await msg.add_reaction("❌")
    except Exception as e:
        await message.reply(f"An error occurred while processing this request. ({e})")


    return reminder_data