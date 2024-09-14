from utility.text import find_currency, unwrap_number
from utility.misc import shit_broke
from utility.convert import get_cur_exchange_rate

async def convert(message, args, _globals):
    if len(args) == 3:
        amount = unwrap_number(args[0])
        currency = find_currency(args[1], _globals['currencies'])
        to_currency = find_currency(args[2], _globals['currencies'])
        
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