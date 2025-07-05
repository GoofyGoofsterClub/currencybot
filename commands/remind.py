import re
import asyncio
from datetime import datetime
import dateparser

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

    reminder_data = {
        "remindee_id": remindee_id,
        "reminder_text": reminder_text,
        "timestamp": timestamp,
        "channel_id": message.channel.id
    }

    confirmation_text = (
        f"Reminder set for <@{remindee_id}> about \"{reminder_text}\" "
        f"at <t:{timestamp}:F>."
    )
    
    try:
        await asyncio.to_thread(_globals['currdb']['reminders'].insert_one, reminder_data)
    except Exception as e:
        await message.reply(f"An error occurred while processing this request. ({e})")
        return
    
    await message.reply(confirmation_text)
    return reminder_data