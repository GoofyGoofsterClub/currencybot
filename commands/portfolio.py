import asyncio
from datetime import datetime, timedelta

from commands.betastock import get_stock, get_stock_records
from utility.crypto import get_crypto_rate
from utility.convert import get_cur_exchange_rate

async def portfolio(message, args, _globals):
    db = _globals['currdb']['user_portfolios']
    summary_db = _globals['currdb']['portfolio_summary']
    user_id = message.author.id

    if not args:
        await _display_portfolio(message, db, summary_db, user_id)
        return

    if len(args) == 4:
        await _modify_portfolio(message, args, db, user_id)
    else:
        await message.reply("Invalid command format. Use `portfolio [add|set|reduce|remove|set-initial] [stock|crypto] [SYMBOL] [value]` or just `portfolio`.")

async def _update_and_get_entry(entry, db):
    asset_type = entry['type']
    symbol = entry['symbol']
    
    fresh_data = await _fetch_asset_data(asset_type, symbol)
    
    if fresh_data and fresh_data.get('price') is not None:
        new_price = fresh_data['price']
        await asyncio.to_thread(
            db.update_one,
            {"_id": entry["_id"]},
            {"$set": {"recent_price": new_price}}
        )
        entry['recent_price'] = new_price
        
    return entry

async def _display_portfolio(message, db, summary_db, user_id):
    status_message = await message.reply("Refreshing your portfolio with the latest prices...")

    user_summary = await asyncio.to_thread(summary_db.find_one, {"user_id": user_id})
    last_checked_value = user_summary.get('last_checked_value') if user_summary else None
    last_checked_currency = user_summary.get('last_checked_currency') if user_summary else None

    entries_cursor = await asyncio.to_thread(db.find, {"user_id": user_id})
    entries = await asyncio.to_thread(list, entries_cursor)

    if not entries:
        await status_message.edit(content="Your portfolio is empty. Add an asset with `portfolio add [stock|crypto] [SYMBOL] [amount]`.")
        return

    update_tasks = [_update_and_get_entry(entry, db) for entry in entries]
    updated_entries = await asyncio.gather(*update_tasks)

    target_currency = updated_entries[0]['currency']
    
    unique_currencies = {entry['currency'] for entry in updated_entries}
    if last_checked_currency:
        unique_currencies.add(last_checked_currency)

    exchange_rates = {target_currency: 1.0}
    currencies_to_fetch = [c for c in unique_currencies if c != target_currency]
    rate_tasks = [asyncio.to_thread(get_cur_exchange_rate, c, target_currency) for c in currencies_to_fetch]
    
    fetched_rates = await asyncio.gather(*rate_tasks)
    for currency, rate in zip(currencies_to_fetch, fetched_rates):
        exchange_rates[currency] = rate if rate else None
    
    if last_checked_value and last_checked_currency != target_currency:
        rate = exchange_rates.get(last_checked_currency)
        last_checked_value = last_checked_value * rate if rate else None

    response_lines = [f"## {message.author.mention}'s Portfolio (in {target_currency}):"]
    total_initial_value = 0.0
    total_current_value = 0.0
    failed_assets = []

    for entry in updated_entries:
        rate = exchange_rates.get(entry['currency'])
        if not rate:
            failed_assets.append(entry['symbol'])
            continue

        initial_investment = entry.get('initial_price', 0) * entry.get('amount', 0)
        current_value = entry.get('recent_price', 0) * entry.get('amount', 0)
        
        total_initial_value += initial_investment * rate
        total_current_value += current_value * rate
        
        try:
            percentage_diff = (current_value - initial_investment) / initial_investment * 100
        except ZeroDivisionError:
            percentage_diff = 0
            
        change_icon = "<:arrowup:1386044488144916752>" if current_value >= initial_investment else "<:arrowdown:1386044531039928452>"
        
        response_lines.append(
            f"◉ **{entry['amount']} {entry['symbol']}** (`{entry['name']}`) `{entry['type'].capitalize()}` "
            f"→ **{current_value * rate:,.2f} {target_currency}** ({entry.get('recent_price', 0) * rate:,.2f} per) {change_icon} {percentage_diff:+.2f}%"
        )
    
    if failed_assets:
        response_lines.append(f"\nCould not fetch exchange rates for {', '.join(failed_assets)}; they were excluded from totals.")

    summary_lines = [f"\nTotal → **{total_current_value:,.2f} {target_currency}**"]
    
    try:
        total_diff_initial = (total_current_value - total_initial_value) / total_initial_value * 100
    except ZeroDivisionError:
        total_diff_initial = 0
    icon_initial = "<:arrowup:1386044488144916752>" if total_current_value >= total_initial_value else "<:arrowdown:1386044531039928452>"
    summary_lines[0] += f" {icon_initial} {total_diff_initial:+.2f}% (from {total_initial_value:,.2f})"

    if last_checked_value is not None:
        try:
            total_diff_last = (total_current_value - last_checked_value) / last_checked_value * 100
        except ZeroDivisionError:
            total_diff_last = 0
        icon_last = "<:arrowup:1386044488144916752>" if total_current_value >= last_checked_value else "<:arrowdown:1386044531039928452>"
        summary_lines[0] += f"   •   {icon_last} {total_diff_last:+.2f}% (from {last_checked_value:,.2f}) since last checked"
    
    response_lines.extend(summary_lines)

    await asyncio.to_thread(
        summary_db.update_one,
        {"user_id": user_id},
        {"$set": {
            "last_checked_value": total_current_value,
            "last_checked_currency": target_currency,
            "user_id": user_id
        }},
        upsert=True
    )
    
    await status_message.edit(content="\n".join(response_lines))

async def _modify_portfolio(message, args, db, user_id):
    operation, asset_type, symbol, value_str = [arg.lower() for arg in args]
    symbol = symbol.upper()

    if operation not in ["add", "set", "reduce", "remove", "set-initial"]:
        await message.reply("Invalid operation. Must be one of `add`, `set`, `reduce`, `remove`, `set-initial`.")
        return
    
    if asset_type not in ["stock", "crypto"]:
        await message.reply("Invalid asset type. Must be `stock` or `crypto`.")
        return

    try:
        value = float(value_str) if operation != 'remove' else 0
        if value < 0:
            raise ValueError
    except ValueError:
        await message.reply("Invalid value. Please provide a positive number.")
        return

    asset_data = await _fetch_asset_data(asset_type, symbol)
    if not asset_data:
        await message.reply(f"Could not find data for {asset_type} symbol '{symbol}'.")
        return

    query_filter = {"user_id": user_id, "symbol": asset_data['symbol'], "type": asset_type}

    if operation == "set-initial":
        new_initial_price = value
        result = await asyncio.to_thread(
            db.update_one,
            query_filter,
            {"$set": {"initial_price": new_initial_price}}
        )
        if result.matched_count > 0:
            await message.reply(f"Updated initial price for **{asset_data['name']}** to `{new_initial_price:,.2f}`.")
        else:
            await message.reply(f"You do not own **{asset_data['name']}**. Add it to your portfolio first.")
        return

    amount = value

    if operation == "remove":
        result = await asyncio.to_thread(db.delete_one, query_filter)
        if result.deleted_count > 0:
            await message.reply(f"Successfully removed **{asset_data['name']}** from your portfolio.")
        else:
            await message.reply(f"You don't own **{asset_data['name']}** in your portfolio.")
        return

    if operation == "reduce":
        user_entry = await asyncio.to_thread(db.find_one, query_filter)
        if not user_entry or user_entry.get('amount', 0) < amount:
            await message.reply(f"You don't have enough **{asset_data['name']}** to reduce by that amount.")
            return

        update_doc = {
            "$inc": {"amount": -amount},
            "$set": {"recent_price": asset_data['price']}
        }
        await asyncio.to_thread(db.update_one, query_filter, update_doc)
        await message.reply(f"Reduced **{asset_data['name']}** by `{amount}`.")
        return

    if operation in ["add", "set"]:
        update_op = {"$inc": {"amount": amount}} if operation == "add" else {"$set": {"amount": amount}}
        set_always = {"recent_price": asset_data['price']}
        set_on_insert = {
            "user_id": user_id,
            "type": asset_type,
            "name": asset_data['name'],
            "symbol": asset_data['symbol'],
            "currency": asset_data['currency'],
            "initial_price": asset_data['price'],
            "inserted_date": int(datetime.now().timestamp())
        }
        if operation == "set":
            set_on_insert["amount"] = amount
            
        update_doc = {**update_op, "$set": set_always, "$setOnInsert": set_on_insert}
        await asyncio.to_thread(db.update_one, query_filter, update_doc, upsert=True)
        action_word = "Added" if operation == "add" else "Set"
        await message.reply(f"{action_word} **{asset_data['name']}** in your portfolio to `{amount}` units.")

async def _fetch_asset_data(asset_type, symbol):
    if asset_type == "stock":
        search_result = await get_stock(symbol)
        if not search_result:
            return None

        end_date = datetime.today()
        start_date = end_date - timedelta(days=5)

        records = await get_stock_records(search_result.symbol, search_result.country, start_date, end_date)
        if not records:
            return None

        return {
            "name": search_result.name,
            "symbol": search_result.symbol,
            "price": records[-1]['Close'],
            "currency": records[0]['Currency']
        }

    elif asset_type == "crypto":
        crypto_data = await asyncio.to_thread(get_crypto_rate, symbol)
        if not crypto_data:
            return None
        return {
            "name": crypto_data['name'],
            "symbol": crypto_data['cc'].upper(),
            "price": crypto_data['price'],
            "currency": "USD"
        }
    return None