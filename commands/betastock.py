import pynvesting
from datetime import datetime, timedelta

def parse_args(args):
    symbol = args[0]
    params = {}
    for arg in args[1:]:
        if arg.startswith('-') and '=' in arg:
            key, value = arg.split('=', 1)
            params[key.lstrip('-')] = value
    return symbol, params


async def stock(message, args, _globals):
    arg_stock, params = parse_args(args)

    end_date = datetime.today()
    start_date = end_date - timedelta(days=30)
    
    search_result = pynvesting.search_quotes(text=arg_stock, products=['stocks'], n_results=1)

    print(search_result)

    df = pynvesting.get_stock_historical_data(stock=search_result.symbol,
        from_date=start_date.strftime('%d/%m/%Y'),
        country=search_result.country,
        to_date=end_date.strftime('%d/%m/%Y'))
    
    print(df)

    records = df.reset_index().to_dict(orient='records')

    rf = pynvesting.get_stock_recent_data(stock=search_result.symbol, country=search_result.country, as_json=False, order='descending', interval='Daily')
    recent_price = rf['Close'].iloc[0]
    recent_date = int(records[-1]['Date'].timestamp())

    try:
        date_change = int(params.get('d', 1))
    except:
        await message.reply("Error parsing parameters.")
        return
    
    print(date_change)

    if date_change > 0:
        try:
            date_change += 1
            difference = round(recent_price - records[-date_change]['Close'], 2)
            difference_percentage = round((difference / records[-date_change]['Close']) * 100, 2)
            difference_date = int(records[-date_change]['Date'].timestamp())
            difference_emoji = "<:arrowdown:1386044531039928452>" if difference < 0 else "<:arrowup:1386044488144916752>"
        except:
            await message.reply("Couldn't fetch data.")
            return
    else:
        await message.reply("Incorrect date frame specified.")
        return

    print(rf)

    print("RECENT  ::: " + str(recent_price))
    print(records)

    response_message = f"""The currnet price of {search_result.name} (`{search_result.symbol}`) is **{recent_price} {records[0]['Currency']}** on {search_result.exchange} exchange as of <t:{recent_date}:f>. The {difference_emoji} {difference} {records[0]['Currency']} difference ({difference_percentage}%) from <t:{difference_date}:R>."""

    msg = await message.reply(response_message)
    await msg.add_reaction('💹')

    return

