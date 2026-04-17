from playwright.sync_api import sync_playwright
import pandas as pd
import re
import time

def scrape_ps4_catalog(max_clicks=80):
    products = []
    seen_titles = set()
    
    print("🚀 Iniciando scraper de Juegos PS4 - ZonaDigitalMD")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("📄 Abriendo la página...")
        page.goto("https://zonadigitalmd.com/productos/juegosps4", wait_until="networkidle")
        
        # Espera larga inicial porque la página es lenta
        print("⏳ Esperando que cargue el JavaScript (15 segundos)...")
        page.wait_for_timeout(15000)
        
        clicks = 0
        print("🔄 Intentando cargar más productos...")
        
        while clicks < max_clicks:
            # Scroll fuerte
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            
            try:
                # Buscar botón de forma muy flexible
                ver_mas = page.get_by_text(re.compile("ver más", re.I)).first
                if not ver_mas.is_visible(timeout=3000):
                    ver_mas = page.locator("button, a").filter(has_text=re.compile("ver más", re.I)).first
                
                if ver_mas.is_visible() and ver_mas.is_enabled():
                    print(f"   → Clic {clicks+1} en 'Ver más productos'")
                    ver_mas.scroll_into_view_if_needed()
                    ver_mas.click()
                    time.sleep(5)
                    clicks += 1
                else:
                    print("   Botón 'Ver más' ya no visible.")
                    break
            except:
                break
        
        # DIAGNÓSTICO importante
        print("\n🔍 DIAGNÓSTICO:")
        print(f"   Productos detectados con selector común: {page.locator('li.product, .product, article.product').count()}")
        print(f"   Elementos con clase que contiene 'product': {page.locator('[class*=\"product\"]').count()}")
        
        # Extraer con selectores más amplios
        print("📊 Extrayendo productos...")
        items = page.locator("li, article, div").filter(has=page.locator("text=/\\$/")).all()  # items que tengan símbolo de precio
        
        for item in items:
            try:
                # Título (cualquier heading o link grande)
                title = ""
                for selector in [".woocommerce-loop-product__title", "h2", "h3", "a"]:
                    elem = item.locator(selector).first
                    if elem.count() > 0:
                        title = elem.inner_text(timeout=3000).strip()
                        if len(title) > 15:
                            break
                
                if not title or title in seen_titles or len(title) < 10:
                    continue
                seen_titles.add(title)
                
                # Precio
                price = "No disponible"
                price_elem = item.locator("text=/\\d+[.,]\\d+/").first
                if price_elem.count() > 0:
                    price = price_elem.inner_text(timeout=3000).strip()
                    price = re.sub(r'\s+', ' ', price).strip()
                
                link = item.locator("a").first.get_attribute("href")
                if link and not link.startswith("http"):
                    link = "https://zonadigitalmd.com" + link
                
                products.append({
                    "Título": title,
                    "Precio": price,
                    "Enlace": link or ""
                })
            except:
                continue
        
        browser.close()
    
    if not products:
        print("\n❌ Todavía no se encontraron productos.")
        print("   La página carga todo con JavaScript y es difícil de scrapear automáticamente.")
        print("   Te recomiendo probar la versión que usa la API interna (más confiable).")
        return
    
    df = pd.DataFrame(products)
    df.to_excel("juegos_ps4_zonadigitalmd.xlsx", index=False)
    print(f"\n🎉 ¡Éxito! Se extrajeron {len(products)} productos.")
    print("Archivo: juegos_ps4_zonadigitalmd.xlsx")

if __name__ == "__main__":
    scrape_ps4_catalog()
