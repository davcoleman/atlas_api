"""
Amazon product scraper.
Extracts: title, price, currency, image, description, ASIN, rating, reviews,
availability, dimensions, weight from any Amazon product URL.

Handles:
  - Standard URLs:  amazon.com/dp/ASIN  |  amazon.com/gp/product/ASIN
  - Named URLs:     amazon.com/Product-Name/dp/ASIN/ref=...
  - Short URLs:     a.co/d/ASIN  (followed via redirect)
  - Regional:       amazon.co.uk, amazon.ca, amazon.com.au, amazon.de …
"""

import re
import json
import httpx
from typing import Optional
from dataclasses import dataclass, field
from bs4 import BeautifulSoup


# ── Rotating headers to avoid trivial bot detection ──────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

_ASIN_RE = re.compile(r"/(?:dp|gp/product|product)/([A-Z0-9]{10})", re.IGNORECASE)


@dataclass
class ScrapedProduct:
    url: str
    asin: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    image_url: Optional[str] = None
    description: Optional[str] = None
    availability: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    scrape_success: bool = False
    error: Optional[str] = None


# ── URL helpers ───────────────────────────────────────────────────────────────

def _extract_asin(url: str) -> Optional[str]:
    m = _ASIN_RE.search(url)
    return m.group(1).upper() if m else None


def _normalise_url(url: str) -> str:
    """Return a clean /dp/ASIN URL so we hit the canonical product page."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    asin = _extract_asin(url)
    if asin:
        # Preserve the domain (amazon.co.uk etc.) but strip tracking params
        m = re.match(r"(https?://(?:www\.)?amazon\.[a-z.]+)", url)
        domain = m.group(1) if m else "https://www.amazon.com"
        return f"{domain}/dp/{asin}"
    return url


def _follow_short_url(url: str) -> str:
    """Follow a.co or similar short redirects to get the real Amazon URL."""
    if "a.co" in url or "amzn.to" in url:
        try:
            with httpx.Client(follow_redirects=True, timeout=10, verify=False) as client:
                r = client.head(url, headers=_HEADERS)
                return str(r.url)
        except Exception:
            pass
    return url


# ── Text parsers ──────────────────────────────────────────────────────────────

def _parse_price(soup: BeautifulSoup) -> tuple[Optional[float], str]:
    """Return (price_float, currency_symbol)."""
    # Modern price block
    whole = soup.select_one(".a-price .a-price-whole")
    frac  = soup.select_one(".a-price .a-price-fraction")
    sym   = soup.select_one(".a-price .a-price-symbol")
    if whole:
        try:
            raw = whole.get_text(strip=True).replace(",", "").rstrip(".")
            frac_val = frac.get_text(strip=True) if frac else "00"
            price = float(f"{raw}.{frac_val}")
            currency = sym.get_text(strip=True) if sym else "$"
            return price, currency
        except ValueError:
            pass

    # Fallback selectors
    for sel in [
        "#priceblock_ourprice", "#priceblock_dealprice",
        "#price_inside_buybox", ".priceToPay",
        "#corePrice_feature_div .a-offscreen",
    ]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            nums = re.sub(r"[^\d.]", "", text.replace(",", ""))
            try:
                return float(nums), "$"
            except ValueError:
                pass
    return None, "USD"


def _parse_image(soup: BeautifulSoup) -> Optional[str]:
    # Try the high-res data attribute first
    img = soup.select_one("#landingImage, #imgBlkFront, #ebooksImgBlkFront")
    if img:
        for attr in ("data-old-hires", "data-a-dynamic-image", "src"):
            val = img.get(attr, "")
            if attr == "data-a-dynamic-image" and val:
                try:
                    urls = list(json.loads(val).keys())
                    return urls[0] if urls else None
                except Exception:
                    pass
            elif val and val.startswith("http"):
                return val
    return None


def _parse_weight(soup: BeautifulSoup) -> Optional[float]:
    """Try the product details table for item weight → return kg."""
    for row in soup.select("#productDetails_techSpec_section_1 tr, #detailBullets_feature_div li"):
        text = row.get_text(" ", strip=True).lower()
        if "weight" in text:
            m = re.search(r"([\d.]+)\s*(pound|lb|kg|gram|oz)", text, re.IGNORECASE)
            if m:
                val, unit = float(m.group(1)), m.group(2).lower()
                if unit in ("pound", "lb"):
                    return round(val * 0.453592, 3)
                if unit in ("oz",):
                    return round(val * 0.0283495, 3)
                if unit in ("gram",):
                    return round(val / 1000, 3)
                return round(val, 3)  # already kg
    return None


def _parse_dimensions(soup: BeautifulSoup) -> Optional[str]:
    for row in soup.select("#productDetails_techSpec_section_1 tr, #detailBullets_feature_div li"):
        text = row.get_text(" ", strip=True)
        if re.search(r"dimension|size", text, re.IGNORECASE):
            # grab the value part after the label
            parts = text.split("\u200F:")
            if len(parts) > 1:
                return parts[-1].strip()
            return text.strip()
    return None


def _parse_rating(soup: BeautifulSoup) -> tuple[Optional[float], Optional[int]]:
    rating = None
    reviews = None
    el = soup.select_one("#acrPopover, .a-icon-alt")
    if el:
        m = re.search(r"([\d.]+)\s*out of", el.get("title", "") or el.get_text())
        if m:
            try:
                rating = float(m.group(1))
            except ValueError:
                pass
    el = soup.select_one("#acrCustomerReviewText")
    if el:
        m = re.search(r"([\d,]+)", el.get_text())
        if m:
            try:
                reviews = int(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return rating, reviews


def _parse_description(soup: BeautifulSoup) -> Optional[str]:
    bullets = soup.select("#feature-bullets ul li span:not(.a-list-item)")
    if not bullets:
        bullets = soup.select("#feature-bullets ul li")
    lines = [b.get_text(strip=True) for b in bullets if b.get_text(strip=True)]
    if lines:
        return "\n".join(f"• {l}" for l in lines[:8])

    # Fallback: product description section
    el = soup.select_one("#productDescription p, #productDescription")
    if el:
        return el.get_text(strip=True)[:800]
    return None


def _parse_brand(soup: BeautifulSoup) -> Optional[str]:
    el = soup.select_one("#bylineInfo, #brand")
    if el:
        text = el.get_text(strip=True)
        return re.sub(r"^(Brand:|Visit the|Store)", "", text, flags=re.IGNORECASE).strip()
    return None


def _parse_breadcrumb_category(soup: BeautifulSoup) -> Optional[str]:
    crumbs = soup.select("#wayfinding-breadcrumbs_feature_div ul li a")
    if crumbs:
        return crumbs[-1].get_text(strip=True)
    return None


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_amazon_url(raw_url: str) -> ScrapedProduct:
    result = ScrapedProduct(url=raw_url)
    try:
        # Resolve short links
        url = _follow_short_url(raw_url)
        url = _normalise_url(url)
        result.url = url
        result.asin = _extract_asin(url)

        with httpx.Client(follow_redirects=True, timeout=15, verify=False) as client:
            resp = client.get(url, headers=_HEADERS)

        if resp.status_code != 200:
            result.error = f"Amazon returned HTTP {resp.status_code}. The item may be region-restricted or require sign-in."
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Check for bot/captcha page
        if soup.select_one("form[action*='validateCaptcha']") or "robot" in resp.text[:500].lower():
            result.error = "Amazon returned a CAPTCHA page. Please try again in a moment."
            return result

        # Title
        title_el = soup.select_one("#productTitle, #ebooksProductTitle")
        result.product_name = title_el.get_text(strip=True) if title_el else None

        # Price
        result.price, sym = _parse_price(soup)
        result.currency = "GBP" if sym == "£" else "EUR" if sym == "€" else "USD"

        # Image
        result.image_url = _parse_image(soup)

        # Description / bullets
        result.description = _parse_description(soup)

        # Brand
        result.brand = _parse_brand(soup)

        # Category from breadcrumb
        result.category = _parse_breadcrumb_category(soup)

        # Availability
        avail_el = soup.select_one("#availability span, #outOfStock")
        result.availability = avail_el.get_text(strip=True) if avail_el else "Unknown"

        # Weight & dimensions
        result.weight_kg = _parse_weight(soup)
        result.dimensions = _parse_dimensions(soup)

        # Rating / reviews
        result.rating, result.review_count = _parse_rating(soup)

        result.scrape_success = bool(result.product_name)
        if not result.scrape_success:
            result.error = "Could not extract product details — Amazon may have changed its layout."

    except httpx.TimeoutException:
        result.error = "Request timed out. Amazon may be rate-limiting. Please try again."
    except Exception as e:
        result.error = f"Scrape failed: {str(e)}"

    return result
