# Automatic Currency Conversion Bot

Bot for automatic conversion of currencies in Discord conversations.

> ![Preview](https://thighs.moe/.~C26Jw2Ulz "Preview")

## Dependencies

1. Python 3.10+
2. Discord Bot

## Installation

Just use docker, lol.

```bash
$ git clone https://github.com/GoofyGoofsterClub/currencybot.git
$ cd currencybot
$ vi docker-compose.yaml # Change environment, add discord token and change default currencies
$ docker compose up
```

or manual, local version:

```bash
$ git clone https://github.com/GoofyGoofsterClub/currencybot.git
$ cd currencybot
$ cp .env.example .env
$ vi .env  # Change environment, add discord token and change default currencies
$ set -o allexport && source .env set && set +o allexport
$ python3 bot.py
```

## Features

- [x] Automatic in-conversation currency conversion;
- [x] Command for manual conversion (`$convert 100 USD JPY`);
- [x] Safe math functions;
- [ ] Automatic services price parsing and conversion.
    - [x] Amazon (GLOBAL);
    - [x] Blocket.se (Sweden);
    - [ ] Aliexpress (GLOBAL);
    - [ ] Steam (using their API, GLOBAL);
    - [ ] prisjakt.nu (Sweden);
    - [ ] Alibaba (GLOBAL);
    - [ ] Pricerunner (maybe, GLOBAL);
    - [ ] Avito (Russia);
    - [ ] DNSShop (Russia);
    - [ ] Mercari (Japan);
    - [ ] JMTHY (Japan);
    - [ ] Goonet (Japan);
    - [ ] Carsensor (Japan);
    - [ ] Rakuten Market (Japan);
    - [ ] Yahoo Auctions (Japan);
    - [ ] ABC-Mart (Japan);
    - [ ] ZOZOTown (Japan);
    - [ ] Ebay (GLOBAL);
    - [ ] Etsy (GLOBAL);
    - [ ] Kronofogden Auktion (Sweden);