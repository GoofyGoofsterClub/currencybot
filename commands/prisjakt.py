from utility.text import find_currency, unwrap_number
from utility.misc import shit_broke
from utility.convert import get_cur_exchange_rate
from datetime import datetime
import requests
import discord

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Content-Type': 'application/json',
    'sentry-trace': '8fd92e226754468ea96b8b13f191bac8-9030872a582f8c57-0',
    'Origin': 'https://www.prisjakt.nu',
    'Connection': 'keep-alive',
    'Referer': 'https://www.prisjakt.nu/produkt.php?p=12270296',
    'Cookie': 'pj:session=...; pj:session.sig=...; cf_clearance=...; __cf_bm=...; pj_sid=...',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'TE': 'trailers'
}

url = 'https://www.prisjakt.nu/_internal/bff'

query = """query productPage($id: Int!, $expertsEnabled: Boolean!, $partnerVideosEnabled: Boolean!) {  product(id: $id) {    ...productPage    ...productPageExpertContent @include(if: $expertsEnabled)    prices {      ...priceList    }    initialStatistics {      numberMainOffers      lowestPrice      highestPrice    }    relations {      type      relations {        name        sortPriority        selected      }    }    variants {      id      name      gtin14      sku      attributes {        type        value      }    }    category {      products(limit: 10, sort: "popularity", getProperties: false) {        nodes {          id        }      }    }    popularProducts(onlyFromFeaturedStores: true) {      ...productCarouselFields    }    trendingProducts(onlyFromFeaturedStores: true) {      ...productCarouselFields    }    othersVisitedProducts {      ...productCarouselFields    }    isExpertTopRated    metadata {      title      description    }    partnerVideos(productId: $id) @include(if: $partnerVideosEnabled) {      __typename      author {        avatar {          url        }        name      }      previewImage {        small {          url        }        large {          url        }      }      title      videoId      videoUrl    }    verifiedProductBadge    sanityBadges {      badgeType      badgeImageUrl    }  }  prismicArticles(tags: ["productpage-priceinfo"]) {    nodes {      pathName    }  }}fragment productPage on Product {  id  name  description(html: true)  pathName  stockStatus  releaseDate  noIndex  sanityFaq {    faqTitle    faqItems {      question      answer {        sections {          _key          _type          style          listItem          level          children {            _key            _type            text            marks          }          markDefs {            _key            _type            blank            href          }          listItem        }      }    }  }  userReviewSummary {    rating    count    countTotal  }  aggregatedRatingSummary {    summary {      rating {        score        count      }    }  }  coreProperties: properties(ids: "_core_") {    nodes {      __typename      id      name      type      pretty      prettyVerbose: pretty(mode: verbose)      prettyTable: pretty(mode: table)      ... on PropertyString {        valueId        categoryLink      }      ... on PropertyList {        values        valueIds        categoryLinks      }      ... on PropertyBoolean {        boolean      }    }  }  brand {    id    name    featured    logo    pathName  }  priceSummary {    regular    alternative  }  media {    count    first(width: _280)  }  category {    id    logo    name    pathName    productCollection    hasAdultContent    path {      id      name      pathName    }  }  sparkline {    values  }  popularity {    total    inCategory  }  productDescription {    preamble    descriptionPoints {      title      text    }    articles {      name      url    }  }  dealInfo {    dealPercentage    offers {      shopId      shopOfferId    }  }}fragment priceList on PriceList {  meta {    itemsTotal    storeStatistics {      totalCount      featuredCount    }  }  nodes {    ...priceListItem  }  mobileContractsV2 {    ...mobileContract  }}fragment priceListItem on Price {  __typename  shopOfferId  name  externalUri  primaryMarket  membershipProgram {    name    requiresCompensation  }  stock {    status    statusText  }  condition  availability {    condition    availabilityDate  }  price {    inclShipping    exclShipping    originalCurrency  }  offerPrices {    price {      exclShipping      inclShipping      endDate    }    originalPrice {      exclShipping      inclShipping    }    memberPrice {      exclShipping      inclShipping      endDate    }  }  store {    ...store  }  authorizedDealer  authorizedDealerData {    authorizedDealersDescription    authorizedDealersShortDescription  }  alternativePrices(includeMainPrice: true) {    __typename    shopOfferId    name    externalUri    primaryMarket    stock {      status      statusText    }    condition    availability {      condition      availabilityDate    }    price {      exclShipping      inclShipping      originalCurrency    }    offerPrices {      price {        exclShipping        inclShipping        endDate      }      originalPrice {        exclShipping        inclShipping      }      memberPrice {        exclShipping        inclShipping        endDate      }    }    variantInfo {      size      sizeSystem      colors    }    variantId    shipping {      cheapest {        deliveryDays {          min          max        }        shippingCost        carrier      }      fastest {        deliveryDays {          min          max        }        shippingCost      }      nodes {        deliveryMethod        carrier        deliveryDays {          min          max        }        shippingCost        sustainability        eligibility      }    }    shopHasUniqueShippings    ourChoiceScore    featuredOverride    shippingCampaigns {      id      type      startDate      endDate    }  }  variantInfo {    size    sizeSystem    colors  }  variantId  shipping {    cheapest {      deliveryDays {        min        max      }      shippingCost      carrier      sustainability    }    fastest {      deliveryDays {        min        max      }      shippingCost      carrier      sustainability    }    nodes {      deliveryMethod      carrier      deliveryDays {        min        max      }      shippingCost      sustainability      eligibility    }  }  shopHasUniqueShippings  ourChoiceScore  featuredOverride  membershipLink  promotion {    id    description    startDate    endDate    imageUrl    owner {      id      name      type    }    title    numberOfProducts  }  shippingCampaigns {    id    type    startDate    endDate  }}fragment mobileContract on MobileContractV2 {  __typename  contractId  name  contractMonths  pricePerMonth  dataGB  externalUri  totalPrice  campaignPricePerMonth  campaignDurationMonths  hardwarePricePerMonth  alternativeContracts {    contractId    name    contractMonths    pricePerMonth    dataGB    externalUri    totalPrice    campaignPricePerMonth    campaignDurationMonths    hardwarePricePerMonth    store {      ...store    }  }  store {    ...store  }}fragment store on Store {  id  name  featured  hasLogo  logo(width: _176)  pathName  providedByStore {    generalInformation  }  userReviewSummary {    rating    count    countTotal  }  market  marketplace  countryCode  primaryMarket  currency  payment {    options {      name    }    providers {      name    }  }}fragment productPageExpertContent on Product {  expertContent {    totalCount    experts {      name      avatar      url    }    selected {      ... on ProductPageExpertTest {        __typename        rating        date(format: "D MMMM YYYY")        title        plus        minus        imageWithSize {          src          alt        }        suitedForLong        suitedFor {          headline          text        }        url        expert {          name          avatar          url        }        category {          name        }      }      ... on ProductPageToplist {        __typename        title        url        category {          name        }        expert {          name          avatar          url        }        products {          id          plus          minus          description        }      }    }    tests {      ... on ProductPageExpertTest {        __typename        title        imageWithSize {          src          alt        }        url      }    }    toplists {      toplists {        __typename        title        url        description {          type          data        }        headlineInfo {          url        }        products {          id          plus          minus        }        imageUrl      }    }    guides {      ... on ProductPageExpertGuide {        __typename        title        imageUrl        url      }    }  }}fragment productCarouselFields on CarouselProduct {  id  name  pathName  category  price  url  userReviewSummary {    rating    count  }  aggregatedRating {    score    count  }  imageUrl  isExpertTopRated}
"""

search_query = """
query SearchSuggestions($query: String!) {
  searchSuggestions(query: $query) {
    id
    name
    product {
      id
      name
    }
  }
}
"""

def fetch_product(product_id: int):
    payload = {
        "query": query,
        "variables": {
            "id": product_id,
            "expertsEnabled": True,
            "partnerVideosEnabled": True,
            "campaignId": 4
        },
        "operationName": "productPage"
    }

    response = requests.post(url, headers=headers, json=payload)
    return response.json()

async def prisjakt(message, args, _globals):
    try:
        if len(args) < 1:
            await message.reply("Du måste ange vad du vill söka efter.")
            return
        
        arg_str = " ".join(args)

        response = requests.post(f"https://www.prisjakt.nu/_internal/bff", json={
            "query": "hash:e4ac9354c618e6f18f51509f6c1c8c30ad4888961f2f62fe3848c8977a70409d",
            "variables": {
                "query": arg_str
            }
        },
        headers=headers)
        if response.status_code != 200:
            await message.reply("Hittade ingenting.")
            return


        data = response.json()
        if len(data['data']['searchSuggestions']) == 0:
            await message.reply("Hittade ingenting.")
            return

        small_info = [x for x in data['data']['searchSuggestions'] if x['__typename'] == 'SuggestedProduct']
        best_match_product = small_info[0]

        product_info = fetch_product(int(best_match_product['id']))
        
        product_id = product_info['data']['product']['id']
        product_name = product_info['data']['product']['name']
        product_description = product_info['data']['product']['metadata']['description']
        try:
            product_image = product_info['data']['product']['media']['first']
        except:
            product_image = "https://pricespy-75b8.kxcdn.com/product/standard/280/0.png"
        
        product_prices = [x for x in product_info['data']['product']['prices']['nodes'] if x['stock']['status'] == "in_stock"][:3]

        if len(product_prices) == 0:
            await message.reply("Hittade ingenting.")
            return

        embed = discord.Embed(title=product_name,
                        url=f"https://www.prisjakt.nu/produkt.php?p={product_id}",
                        description=product_description,
                        timestamp=datetime.now())

        embed.set_author(name="Prisjakt",
                        url="https://www.prisjakt.nu/",
                        icon_url="https://pricespy-75b8.kxcdn.com/g/rfe/logos/logo_v2_symbol.png")

        for price in product_prices:
            if price['price']['inclShipping'] != None:
                price_str = f"{price['price']['inclShipping']} {price['store']['currency']} (incl. shipping)"
            else:
                price_str = f"{price['price']['exclShipping']} {price['store']['currency']} (excl. shipping)"

            if price['externalUri'] == "" or price['externalUri'] is None:
                value = f"för {price['name']}\nSkick: `{price['condition']}`\n(länk saknas)"
            else:
                value = f"för {price['name']}\n[Visit]({price['externalUri']})"
            embed.add_field(name=f"{price['store']['name']} ・ **{price_str}**",
                            value=value,
                            inline=False)

        embed.set_thumbnail(url=product_image)

        embed.set_footer(text="Hämtat från Prisjakt",
                        icon_url="https://pricespy-75b8.kxcdn.com/g/rfe/logos/logo_v2_symbol.png")

        await message.reply(embed=embed)

    except Exception as e:
        await message.reply(f"An error occurred while processing this request. ({e})")