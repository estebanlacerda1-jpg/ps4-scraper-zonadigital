from playwright.sync_api import sync_playwright
import pandas as pd
import re

def scrape_ps4_catalog(max_clicks=100):
    products = []
    seen_titles = set()
    
    print("🚀 Iniciando scraper de Juegos PS4...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto("https://zonadigitalmd.com/productos/juegosps4", wait_until="networkidle")
        page.wait_for_timeout(10000)
        
        clicks = 0
        while clicks < max_clicks:
            try:
                # Buscar botón "Ver más productos"
                ver_mas = page.get_by_text(re.compile("ver más", re.I)).first
                if ver_mas.is_visible(timeout=4000) and ver_mas.is_enabled():
                    print(f"   Clic {clicks+1} → Ver más productos")
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
                title = item.locator(".woocommerce-loop-product__title, h2, h3, .product-title").first.inner_text(timeout=3000).strip()
                if not title or title in seen_titles or len(title) < 10:
                    continue
                seen_titles.add(title)
                
                price = "No disponible"
                price_elem = item.locator(".price, .woocommerce-Price-amount, .amount").first
                if price_elem.count() > 0:
                    price = price_elem.inner_text(timeout=3000).strip()
                    price = re.sub(r'\s+', ' ', price).strip()
                
                link = item.locator("a").first.get_attribute("href")
                if link and not link.startswith("http"):
                    link = "https://zonadigitalmd.com" + link
                
                products.append({
                    "Título": title,
                    "Precio": price,
                    "Enlace": link
                })
            except:
                continue
        
        browser.close()
    
    if not products:
        print("❌ No se encontraron productos")
        return
    
    df = pd.DataFrame(products)
    df.to_excel("juegos_ps4_zonadigitalmd.xlsx", index=False)
    print(f"✅ ¡Listo! Se extrajeron {len(products)} productos")

if __name__ == "__main__":
    scrape_ps4_catalog()
