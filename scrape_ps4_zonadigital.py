from playwright.sync_api import sync_playwright
import pandas as pd
import re
import sys

def scrape_ps4_catalog(max_clicks=100, output_file="juegos_ps4_zonadigitalmd.xlsx"):
    products = []
    seen_titles = set()
    
    print("🚀 Iniciando scraper...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://zonadigitalmd.com/productos/juegosps4", wait_until="networkidle")
        page.wait_for_timeout(10000)
        
        clicks = 0
        while clicks < max_clicks:
            try:
                ver_mas = page.get_by_text(re.compile("ver más", re.I)).first
                if ver_mas.is_visible(timeout=5000) and ver_mas.is_enabled():
                    print(f"Clic {clicks+1} en Ver más")
                    ver_mas.scroll_into_view_if_needed()
                    ver_mas.click()
                    page.wait_for_timeout(5000)
                    clicks += 1
                else:
                    break
            except:
                break
        
        # Extraer productos
        items = page.locator("li.product, .product, article.product, [class*='product']").all()
        
        for item in items:
            try:
                title = item.locator(".woocommerce-loop-product__title, h2, h3").first.inner_text(timeout=3000).strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                
                price = item.locator(".price, .woocommerce-Price-amount").first.inner_text(timeout=3000).strip() if item.locator(".price").count() > 0 else "No disponible"
                price = re.sub(r'\s+', ' ', price).strip()
                
                link = item.locator("a").first.get_attribute("href")
                if link and not link.startswith("http"):
                    link = "https://zonadigitalmd.com" + link
                
                products.append({"Título": title, "Precio": price, "Enlace": link})
            except:
                continue
        
        browser.close()
    
    if not products:
        print("❌ No se encontraron productos")
        sys.exit(1)
    
    df = pd.DataFrame(products)
    df.to_excel(output_file, index=False)
    print(f"✅ Se extrajeron {len(products)} productos → {output_file}")

if __name__ == "__main__":
    scrape_ps4_catalog()
