from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio

async def reminders(message, args, _globals):
    reminders = await asyncio.to_thread(_globals['currdb']['reminders'].find, {"remindee_id": message.author.id})

    if not reminders:
        await message.reply("You have no reminders.")
        return

    reminders_list = []
    for idx, reminder in enumerate(reminders, 1):
        reminder_time = datetime.fromtimestamp(reminder['timestamp'], tz=ZoneInfo('UTC')).strftime('%Y-%m-%d %H:%M:%S %Z')
        reminder_id = reminder.get('reminder_id', "(no id)")
        reminders_list.append(f"{idx}. {reminder['reminder_text']} \nTime: {reminder_time}\n-# Reminder ID: `{reminder_id}`")

    if reminders_list:
        split_list = []
        temp_str = ""
        for reminder in reminders_list:
            if len(temp_str) + len(reminder) > 1900:
                split_list.append(temp_str)
                temp_str = ""
            temp_str += reminder + "\n"
        if temp_str:
            split_list.append(temp_str)

        for idx, reminder in enumerate(split_list, 1):
            await message.reply(f"Reminders ({idx}/{len(split_list)}):\n{reminder}")

