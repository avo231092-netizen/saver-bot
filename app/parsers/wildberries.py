import aiohttp
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def parse(url: str) -> dict | None:
    """Parse Wildberries product page and return title + price."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning(f"WB status {resp.status} for {url}")
                    return None
                html = await resp.text()
        # Try API approach first: extract product ID from URL
        m = re.search(r"/(?:catalog|product)/(\d+)", url)
        if m:
            product_id = m.group(1)
            api_url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        products = data.get("data", {}).get("products", [])
                        if products:
                            p = products[0]
                            title = p.get("name", "Без названия")
                            price = p.get("salePriceU", p.get("priceU", 0)) / 100
                            return {"title": title, "price": float(price), "marketplace": "wildberries"}
        # Fallback: parse HTML
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Товар"
        price_match = re.search(r"\"price\":(\d+)", html)
        price = float(price_match.group(1)) if price_match else 0.0
        return {"title": title, "price": price, "marketplace": "wildberries"}
    except Exception as e:
        logger.error(f"WB parse error: {e}")
        return None
