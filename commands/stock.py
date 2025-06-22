import yfinance as yf

def get_stock_info(symbol: str):
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    info = ticker.info
    data = ticker.history(period="1d")
    if data.empty:
        return {"error": "No data found."}
    latest = data.iloc[-1]
    prev_close = ticker.info.get("previousClose", latest["Close"])
    current_price = latest["Close"]
    percent_change = ((current_price - prev_close) / prev_close) * 100

    return {
        "symbol": symbol,
        "name": info.get("longName", "N/A"),
        "price": round(current_price, 2),
        "percent_change": round(percent_change, 2)
    }

async def stock(message, args, _globals):
    await message.reply("i will fix this later")
    return # TODO: Fix this shit
    if len(args) >= 1:
        try:
            st = get_stock_info(args[0])
            if ('error' in st):
                await message.reply(f"An error occurred while processing this request. ({st['error']})")
                return

            if st['percent_change'] > 0:
                change_emote = "<:arrowup:1386044488144916752>"
            else:
                change_emote = "<:arrowdown:1386044531039928452>"
            await message.reply(f"{st['name']} (`{st['symbol']}`) is **{st['price']} USD** ({change_emote} {st['percent_change']}%)")
        except Exception as e:
            await message.reply(f"An error occurred while processing this request. ({e})")
    else:
        await message.reply('Invalid arguments')