import discord
import whoisit
import asyncio
from datetime import datetime
from utility.command import Command

whois_lock = asyncio.Lock()

def domain_to_color(domain):
    res = 0
    for c in domain:
        res += ord(c)
    r = (res * 1103515245 + 12345) % 2**24
    g = (res * 1103515245 + 12345 + 1) % 2**24
    b = (res * 1103515245 + 12345 + 2) % 2**24
    return discord.Color.from_rgb(r % 256, g % 256, b % 256)

async def _whois(message, args, _globals):
    if not whoisit.is_bootstrapped():
        await whoisit.bootstrap_async(overrides=True)
    if not args:
        await message.reply(f"Usage: $whois <domain>")
        return

    domain = args[0]
    if "://" in domain:
        domain = domain.split("://")[1]
    elif "www." in domain:
        domain = domain.split("www.")[1]

    embed = discord.Embed(
        title=f"Domain Info for `{domain}`",
        color=domain_to_color(domain)
    )

    try:
        rdap = await whoisit.domain_async(domain)
    except:
        await message.reply(f"Domain unsupported or not found.")
        return

    try:

        embed.set_thumbnail(url=f"https://image.thum.io/get/maxAge/12/width/700/https://{domain}")
        
        # Dates

        created = rdap['registration_date'].strftime('%Y-%m-%d %H:%M:%S UTC')
        updated = rdap['last_changed_date'].strftime('%Y-%m-%d %H:%M:%S UTC')
        expires = rdap['expiration_date'].strftime('%Y-%m-%d %H:%M:%S UTC')

        embed.add_field(
            name="Created",
            value=created,
            inline=True
        )

        embed.add_field(
            name="Updated",
            value=updated,
            inline=True
        )

        embed.add_field(
            name="Expires",
            value=expires,
            inline=True
        )

        # Entities info

        registrar_name = rdap['entities']['registrar'][0]['name']
        registrar_email = rdap['entities']['registrar'][0]['email']

        embed.add_field(
            name="Registrar",
            value=f"{registrar_name}\n`{registrar_email}`",
            inline=True
        )

        # Registrant

        registrant_name = rdap['entities']['registrant'][0]['name']
        registrant_email = rdap['entities']['registrant'][0]['email']

        embed.add_field(
            name="Registrant",
            value=f"{registrant_name}\n`{registrant_email}`",
            inline=True
        )

        # Nameservers

        nameservers = "\n".join(rdap['nameservers'])
        embed.add_field(
            name="Nameservers",
            value=nameservers,
            inline=False
        )

        await message.reply(embed=embed)
    except Exception as e:
        raise e
        await message.reply(f"Error while processing whois query: {e}")


command = Command(
    ["whois", "rdap"],
    _whois
)