import aiohttp
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def extract_product_id(url: str) -> str | None:
    """Extract product ID from WB URL."""
    # Match patterns: /catalog/123456/ or /product/123456/ or /catalog/123456/detail.aspx
    m = re.search(r"/(?:catalog|product)/(\d+)", url)
    if m:
        return m.group(1)
    # Also try nm= parameter
    m = re.search(r"nm=(\d+)", url)
    if m:
        return m.group(1)
    return None


async def parse(url: str) -> dict | None:
    """Parse Wildberries product page and return title + price."""
    try:
        product_id = extract_product_id(url)
        if not product_id:
            logger.warning(f"WB: cannot extract product ID from {url}")
            return None

        logger.info(f"WB: parsing product {product_id}")

        # Try multiple API endpoints — WB uses different ones for different regions
        api_urls = [
            f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
            f"https://card.wb.ru/cards/v2/detail?appType=1&curr=amd&dest=-593528&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
            f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&nm={product_id}",
            # Older API fallback
            f"https://wbx-content-v2.wbstatic.net/ru/{product_id}.json",
        ]

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers=HEADERS) as session:
            for api_url in api_urls:
                try:
                    async with session.get(api_url) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()

                        # v2 API format
                        products = data.get("data", {}).get("products", [])
                        if products:
                            p = products[0]
                            title = p.get("name", "Без названия")
                            # salePriceU is in kopecks
                            price = p.get("salePriceU", p.get("priceU", 0)) / 100
                            if price > 0:
                                logger.info(f"WB: found via API v2 — {title}, {price}")
                                return {"title": title, "price": float(price), "marketplace": "wildberries"}

                        # Old API format
                        if "data" in data and "products" not in data.get("data", {}):
                            # Try direct fields
                            title = data.get("name", data.get("title", ""))
                            price = data.get("price", data.get("salePrice", 0))
                            if title and price:
                                logger.info(f"WB: found via old API — {title}, {price}")
                                return {"title": title, "price": float(price), "marketplace": "wildberries"}
                except Exception as e:
                    logger.debug(f"WB: API {api_url} failed: {e}")
                    continue

            # Fallback: parse HTML page directly
            logger.info(f"WB: falling back to HTML parsing for {url}")
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning(f"WB: HTML status {resp.status} for {url}")
                    return None
                html = await resp.text()

            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else "Товар Wildberries"

            # Try multiple price patterns
            price = 0.0
            # Pattern 1: "price":12345
            m = re.search(r'"price"\s*:\s*(\d+)', html)
            if m:
                price = float(m.group(1))
            # Pattern 2: salePriceU
            if price == 0:
                m = re.search(r'"salePriceU"\s*:\s*(\d+)', html)
                if m:
                    price = float(m.group(1)) / 100
            # Pattern 3: meta tag
            if price == 0:
                meta = soup.find("meta", {"itemprop": "price"})
                if meta:
                    price = float(meta.get("content", 0))
            # Pattern 4: visible price text
            if price == 0:
                price_tag = soup.find("span", class_=re.compile(r"price", re.I))
                if price_tag:
                    txt = price_tag.get_text(strip=True)
                    m = re.search(r'(\d+[\s\d]*)', txt)
                    if m:
                        price = float(m.group(1).replace(" ", ""))

            if title and price > 0:
                logger.info(f"WB: found via HTML — {title}, {price}")
                return {"title": title, "price": price, "marketplace": "wildberries"}

            logger.warning(f"WB: could not extract price for {url}")
            return None

    except Exception as e:
        logger.error(f"WB parse error: {e}")
        return None
