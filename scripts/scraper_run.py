import hashlib, asyncio, logging, os, re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import httpx
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("infolocal.scraper")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
MUNICIPIO_ID = "1400c5a4-452f-4764-9ec2-6d10898ad285"
FUENTE_AYT   = "4ee24994-ab4f-4c52-ba16-d0374077dc67"
FUENTE_SOY   = "77485e96-00b6-42cd-ac6d-e8ccfb58be87"
BASE_URL     = "https://aytoalgete.es"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; InfoLocalBot/1.0)"}

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

CATEGORIAS = {
    "colegio|escuela|educacion|curso|alumno|campus|instituto": "educacion",
    "fiesta|feria|concierto|teatro|cultura|exposicion|musica|carnaval": "cultura",
    "deporte|futbol|baloncesto|piscina|polideportivo|torneo": "deporte",
    "obra|urbanismo|carril|acera|parque|licencia|construccion": "urbanismo",
    "policia|seguridad|trafico|emergencia|bombero": "seguridad",
    "bus|transporte|cercan|metro|linea|parada": "transporte",
    "salud|hospital|medico|farmacia|vacuna": "salud",
    "ayuda|subvencion|beca|prestacion": "hacienda",
    "familia|menor|infancia|juventud|mayor|natalidad": "familia",
    "alcalde|concejal|pleno|partido|presupuesto|politica": "politica",
}

def clasificar(titulo, cuerpo=""):
    texto = (titulo + " " + (cuerpo or "")).lower()
    for patron, sub in CATEGORIAS.items():
        if re.search(patron, texto):
            return sub
    return "general"

def hash_c(titulo, url):
    return hashlib.sha256(f"{titulo}{url}".encode()).hexdigest()

def ya_existe(h):
    return len(sb.table("contenidos").select("id").eq("hash_contenido", h).execute().data) > 0

def guardar(titulo, resumen, url, categoria, fuente_id, subcategoria="general", etiquetas=None):
    h = hash_c(titulo, url)
    if ya_existe(h):
        return False
    sb.table("contenidos").insert({
        "municipio_id":      MUNICIPIO_ID,
        "fuente_id":         fuente_id,
        "categoria":         categoria,
        "subcategoria":      subcategoria,
        "etiquetas":         etiquetas or ["algete", subcategoria],
        "titulo":            titulo,
        "resumen":           resumen,
        "cuerpo":            resumen,
        "url_original":      url if url.startswith("http") else BASE_URL + url,
        "fecha_publicacion": datetime.now(timezone.utc).isoformat(),
        "hash_contenido":    h,
        "activo":            True,
        "es_alerta":         False,
        "procesado_ia":      True,
    }).execute()
    log.info(f"  ✓ [{subcategoria}] {titulo[:65]}")
    return True

def slug_to_titulo(url):
    try:
        slug = url.split("id=")[1].split("&")[0]
        slug = slug.split(":")[1] if ":" in slug else slug
        return slug.replace("-", " ").strip().capitalize()
    except Exception:
        return None

async def main():
    log.info("═══ InfoLocal Scraper ═══")
    total = nuevos = 0

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Ayuntamiento de Algete
        r = await client.get(BASE_URL, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "lxml")
        for item in soup.select(".news"):
            for a in item.select("a"):
                href = a.get("href", "")
                if "com_k2" not in href or "view=item" not in href:
                    continue
                txt = a.get_text(strip=True)
                titulo = txt if (txt and len(txt) > 8 and txt.lower() not in ["leer más","leer mas","ver"]) else slug_to_titulo(href)
                if not titulo:
                    continue
                p = item.select_one("p, .catItemIntroText")
                resumen = p.get_text(strip=True)[:300] if p else titulo
                sub = clasificar(titulo, resumen)
                total += 1
                if guardar(titulo, resumen, href, "noticia", FUENTE_AYT, sub, ["algete", sub, "ayuntamiento"]):
                    nuevos += 1
                break

        # SoyDeAlgete
        r2 = await client.get("https://www.soydemadrid.com/noticias-algete/", headers=HEADERS, timeout=20)
        soup2 = BeautifulSoup(r2.text, "lxml")
        for art in soup2.select("article")[:15]:
            for a in art.select("a"):
                txt = a.get_text(strip=True)
                if len(txt) < 20 or any(x in txt.lower() for x in ["leer","ver más","compartir"]):
                    continue
                if "algete" not in (art.get_text(strip=True) + txt).lower():
                    continue
                url = a.get("href", "")
                if not url.startswith("http"):
                    url = "https://www.soydemadrid.com" + url
                p = art.select_one("p, .excerpt")
                resumen = p.get_text(strip=True)[:300] if p else txt
                sub = clasificar(txt, resumen)
                total += 1
                if guardar(txt, resumen, url, "noticia", FUENTE_SOY, sub, ["algete", sub, "local"]):
                    nuevos += 1
                break

    sb.table("scraping_log").insert({
        "fuente_id": FUENTE_AYT,
        "items_encontrados": total,
        "items_nuevos": nuevos,
        "estado": "ok"
    }).execute()
    log.info(f"✅ {nuevos} nuevos de {total}")

asyncio.run(main())
