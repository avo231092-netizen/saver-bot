import re
import json
import logging
import asyncio
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_product_id(url: str) -> str | None:
    m = re.search(r"/(?:catalog|product)/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"nm=(\d+)", url)
    if m:
        return m.group(1)
    return None


def _try_api(product_id: str) -> dict | None:
    """Try WB API with browser TLS fingerprint."""
    api_urls = [
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=amd&dest=-593528&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
        f"https://catalog.wb.ru/catalog/card/v1?nm={product_id}",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Referer": "https://www.wildberries.ru/",
        "Origin": "https://www.wildberries.ru",
    }
    for api_url in api_urls:
        try:
            resp = cffi_requests.get(api_url, headers=headers, impersonate="chrome120", timeout=15)
            if resp.status_code != 200:
                continue
            text = resp.text
            if not text.startswith("{"):
                continue
            data = json.loads(text)
            products = data.get("data", {}).get("products", [])
            if products:
                p = products[0]
                title = p.get("name", "Без названия")
                price = p.get("salePriceU", p.get("priceU", 0)) / 100
                if price > 0:
                    logger.info(f"WB: found via API — {title}, {price}")
                    return {"title": title, "price": float(price), "marketplace": "wildberries"}
        except Exception as e:
            logger.debug(f"WB API {api_url[:70]} failed: {e}")
    return None


def _try_html(url: str, product_id: str) -> dict | None:
    """Try parsing HTML page with browser TLS fingerprint."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    # Try both .am and .ru domains
    urls = [
        url,
        f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
    ]
    for try_url in urls:
        try:
            resp = cffi_requests.get(try_url, headers=headers, impersonate="chrome120", timeout=20, allow_redirects=True)
            if resp.status_code not in (200, 307):
                continue
            html = resp.text
            if len(html) < 500:
                continue
            
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).split(" — ")[0].split(" | ")[0]
            if not title:
                title = "Товар Wildberries"
            
            price = 0.0
            for pattern in [r'"salePriceU"\s*:\s*(\d+)', r'"priceU"\s*:\s*(\d+)', r'"price"\s*:\s*(\d+)']:
                m = re.search(pattern, html)
                if m:
                    val = int(m.group(1))
                    price = val / 100 if val > 1000 else float(val)
                    break
            if price == 0:
                meta = soup.find("meta", {"itemprop": "price"})
                if meta:
                    price = float(meta.get("content", 0))
            if price == 0:
                for cls in ["price-block__final-price", "catalog-page__price", "product-page__price"]:
                    tag = soup.find("span", class_=cls) or soup.find("div", class_=cls)
                    if tag:
                        txt = tag.get_text(strip=True)
                        m = re.search(r'(\d+[\s\d]*)', txt)
                        if m:
                            price = float(m.group(1).replace(" ", "").replace("\xa0", ""))
                            break
            
            if title and price > 0:
                logger.info(f"WB: found via HTML — {title}, {price}")
                return {"title": title, "price": price, "marketplace": "wildberries"}
        except Exception as e:
            logger.debug(f"WB HTML {try_url[:70]} failed: {e}")
    return None


async def parse(url: str) -> dict | None:
    """Parse Wildberries product using curl_cffi for anti-bot bypass."""
    try:
        product_id = extract_product_id(url)
        if not product_id:
            logger.warning(f"WB: cannot extract product ID from {url}")
            return None
        
        logger.info(f"WB: parsing product {product_id}")
        
        # Run blocking curl_cffi in thread pool
        loop = asyncio.get_event_loop()
        
        # 1. Try API
        result = await loop.run_in_executor(None, _try_api, product_id)
        if result:
            return result
        
        # 2. Try HTML
        result = await loop.run_in_executor(None, _try_html, url, product_id)
        if result:
            return result
        
        logger.warning(f"WB: all methods failed for product {product_id}")
        return None
    except Exception as e:
        logger.error(f"WB parse error: {e}")
        return None
