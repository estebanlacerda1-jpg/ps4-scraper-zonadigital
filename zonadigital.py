#!/usr/bin/env python3
"""Prueba de catálogo de ZonaDigitalMD. Solo imprime; no genera archivos."""
from __future__ import annotations

import re
import sys
import time
import unicodedata
from collections import defaultdict
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

BASE = "https://zonadigitalmd.com"
CATALOG_URL = f"{BASE}/productos"
MAX_PAGES = 40
NO_NEW_PAGES_TO_STOP = 2
REQUEST_DELAY = 0.6
TIMEOUT = 30

# Categorías elegidas. Se resuelven desde el menú real del sitio para no
# depender de slugs inventados o antiguos. Nintendo, preventas, 2x1 y
# accesorios quedan deliberadamente fuera.
INCLUDED_CATEGORIES = {
    "PS PLUS 1 CONSOLA PS4/PS5",
    "JUEGOS PS4",
    "JUEGOS PS5",
    "JUEGOS PC CODIGO",
    "JUEGOS PC CUENTA",
    "JUEGOS XBOX",
    "CODIGO WINDOWS",
    "CODIGO AVAST",
    "MONEDAS APEX LEGENDS",
    "GIFT CARD FORTNITE V",
    "GIFT CARD PS4/PS5",
    "GIFT CARD STEAM",
    "GIFT CARD ROBLOX",
    "GIFT CARD XBOX",
    "GIFT CARD BATTLENET",
    "GIFT CARD RIOT LATAM",
    "GIFT CARD FREE FIRE",
    "GIFT CARD GOOGLE PLAY USA",
    "GIFT CARD APPLE USA",
    "GIFT CARD USA",
    "XBOX GAME PASS",
    "CODIGO EA PLAY",
}

ALIASES = {
    "GIFT CARD FORTNITE V": {"GIFT CARD FORTNITE V", "CARGA FORTNITE V"},
    "XBOX GAME PASS": {"XBOX GAME PASS", "XBOX GAME PASS CODIGO"},
    "CODIGO EA PLAY": {"CODIGO EA PLAY", "EA PLAY CODIGO"},
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.7",
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value).strip().upper()
    return value


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def category_links(session: requests.Session):
    soup = get_soup(session, CATALOG_URL)
    found = {}
    for anchor in soup.select("a[href]"):
        label = normalize(anchor.get_text(" ", strip=True))
        href = anchor.get("href", "").strip()
        if not label or not href:
            continue
        for canonical in INCLUDED_CATEGORIES:
            accepted = ALIASES.get(canonical, {canonical})
            if label in accepted:
                found.setdefault(canonical, urljoin(BASE, href))
    return found


def page_url(category_url: str, page_number: int) -> str:
    parsed = urlparse(category_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["page"] = [str(page_number)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def extract_products(soup: BeautifulSoup, category: str):
    # El sitio utiliza componentes custom app-item-gift y IDs product-N.
    cards = soup.select("app-item-gift")
    if not cards:
        cards = soup.select('[id^="product-"]')

    extracted = []
    for card in cards:
        title_node = card.select_one(
            ".item-gift__content-title, [class*='content-title'], h2, h3"
        )
        title = title_node.get_text(" ", strip=True) if title_node else ""

        link_node = card.select_one("a[href]")
        link = urljoin(BASE, link_node["href"]) if link_node else ""

        price_node = card.select_one(
            "app-item-price-gift .price, .price, [class*='price']"
        )
        price = price_node.get_text(" ", strip=True) if price_node else ""

        raw_id = card.get("id", "")
        match = re.search(r"product-(\d+)", raw_id)
        product_id = match.group(1) if match else ""

        # En algunos diseños el ID puede estar en un descendiente.
        if not product_id:
            id_node = card.select_one('[id^="product-"]')
            if id_node:
                match = re.search(r"product-(\d+)", id_node.get("id", ""))
                product_id = match.group(1) if match else ""

        if not title and link:
            title = link_node.get_text(" ", strip=True)
        if not title or not link:
            continue

        key = product_id or link.rstrip("/")
        extracted.append({
            "id": product_id or "sin-id",
            "key": key,
            "categoria": category,
            "nombre": re.sub(r"\s+", " ", title).strip(),
            "precio": re.sub(r"\s+", " ", price).strip(),
            "url": link,
        })
    return extracted


def scrape_category(session: requests.Session, category: str, url: str):
    products = {}
    previous_count = -1
    stagnant_pages = 0
    pages_read = 0

    for page_number in range(1, MAX_PAGES + 1):
        target = page_url(url, page_number)
        try:
            soup = get_soup(session, target)
        except requests.RequestException as exc:
            if page_number == 1:
                raise RuntimeError(f"falló la primera página: {exc}") from exc
            print(f"  ⚠️ Página {page_number}: error de petición: {exc}")
            break

        batch = extract_products(soup, category)
        before = len(products)
        for product in batch:
            products.setdefault(product["key"], product)
        new_count = len(products) - before
        pages_read = page_number

        print(
            f"  Página {page_number}: {len(batch)} tarjetas visibles; "
            f"{new_count} productos nuevos; acumulado único {len(products)}"
        )

        # La paginación del sitio es acumulativa: page=N vuelve a incluir
        # los anteriores. Dos páginas seguidas sin nuevos IDs indican fin.
        if len(products) == previous_count or new_count == 0:
            stagnant_pages += 1
        else:
            stagnant_pages = 0
        previous_count = len(products)

        if stagnant_pages >= NO_NEW_PAGES_TO_STOP:
            break
        time.sleep(REQUEST_DELAY)

    return list(products.values()), pages_read


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 72)
    print("ZONADIGITALMD — PRUEBA DE SCRAPER (SIN ARCHIVOS)")
    print("=" * 72)

    try:
        discovered = category_links(session)
    except requests.RequestException as exc:
        print(f"ERROR: no se pudo leer el catálogo: {exc}")
        return 1

    missing = sorted(INCLUDED_CATEGORIES - set(discovered))
    print(f"Categorías elegidas encontradas en el menú: {len(discovered)}")
    for name, url in sorted(discovered.items()):
        print(f"  ✓ {name}: {url}")
    if missing:
        print("\nCategorías elegidas que no aparecen en el menú:")
        for name in missing:
            print(f"  - {name}")

    all_products = {}
    errors = []
    summary = []

    for category, url in sorted(discovered.items()):
        print(f"\n[{category}]")
        try:
            products, pages = scrape_category(session, category, url)
            summary.append((category, len(products), pages, "OK"))
            for product in products:
                # Dedupe global por ID/URL sin perder categoría de origen.
                key = product["key"]
                if key in all_products:
                    all_products[key]["categorias"].add(category)
                else:
                    all_products[key] = {
                        **product,
                        "categorias": {category},
                    }
        except Exception as exc:
            errors.append((category, str(exc)))
            summary.append((category, 0, 0, "ERROR"))
            print(f"  ❌ {exc}")

    print("\n" + "=" * 72)
    print("RESUMEN POR CATEGORÍA")
    print("=" * 72)
    for category, count, pages, status in summary:
        print(f"{status:5} | {count:4} productos | {pages:2} páginas | {category}")

    print("\n" + "=" * 72)
    print(f"TOTAL ÚNICO GLOBAL: {len(all_products)}")
    print(f"CATEGORÍAS LEÍDAS: {len(summary)}")
    print(f"CATEGORÍAS CON ERROR: {len(errors)}")
    print("=" * 72)

    print("\nPRODUCTOS DETECTADOS")
    for product in sorted(all_products.values(), key=lambda p: p["nombre"].casefold()):
        categories = ", ".join(sorted(product["categorias"]))
        print(
            f"- [{categories}] {product['nombre']} | "
            f"{product['precio'] or 'PRECIO NO DETECTADO'} | {product['url']}"
        )

    # Cualquier error de categoría hace fallar el job para que sea visible.
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
