# ============================================================
#  InfoLocal — Scraper de producción v2
#  Fuentes: Ayuntamiento Algete, SoyDeAlgete,
#           Madrid Norte 24h, Madrid 24 Horas,
#           Madrid Es Noticia, El Diario de Madrid
#  Cron: cada día a las 7:00h via Render
# ============================================================
import hashlib, asyncio, logging, os, re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
import httpx
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("infolocal.scraper")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
MUNICIPIO_ID = "1400c5a4-452f-4764-9ec2-6d10898ad285"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; InfoLocalBot/1.0)"}

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Fuentes ──────────────────────────────────────────────────
FUENTES = {
    "Ayuntamiento de Algete": {
        "url": "https://aytoalgete.es", "tipo": "web",
        "id": "4ee24994-ab4f-4c52-ba16-d0374077dc67"
    },
    "SoyDeAlgete": {
        "url": "https://www.soydemadrid.com/noticias-algete/", "tipo": "web",
        "id": "77485e96-00b6-42cd-ac6d-e8ccfb58be87"
    },
    "Madrid Norte 24h": {
        "url": "https://www.madridnorte24horas.com/rss/", "tipo": "rss"
    },
    "Madrid 24 Horas": {
        "url": "https://www.madrid24horas.com/tags/algete/", "tipo": "web"
    },
    "Madrid Es Noticia": {
        "url": "https://www.madridesnoticia.es/secciones/municipios/algete/", "tipo": "web"
    },
    "El Diario de Madrid": {
        "url": "https://www.eldiariodemadrid.es/tags/algete/", "tipo": "web"
    },
}

CATEGORIAS = {
    "colegio|escuela|educacion|curso|alumno|campus|instituto|agendas": "educacion",
    "fiesta|feria|concierto|teatro|cultura|exposicion|musica|carnaval|fiestas|dj": "cultura",
    "deporte|futbol|baloncesto|piscina|polideportivo|torneo|atletismo|ciclismo": "deporte",
    "obra|urbanismo|carril|acera|parque|licencia|construccion|asfalt": "urbanismo",
    "policia|seguridad|trafico|emergencia|bombero|encierro|accidente|pulseras": "seguridad",
    "bus|transporte|cercan|metro|linea|parada|c4a": "transporte",
    "salud|hospital|medico|farmacia|vacuna|natalidad|ambulancia": "salud",
    "ayuda|subvencion|beca|prestacion|instaladores|empleo": "hacienda",
    "familia|menor|infancia|juventud|mayor|natalidad|concejal": "familia",
    "alcalde|concejal|pleno|partido|presupuesto|politica|vox|pp|psoe|vecinos por|sueldo|judicial": "politica",
}

def clasificar(texto):
    t = texto.lower()
    for patron, sub in CATEGORIAS.items():
        if re.search(patron, t):
            return sub
    return "general"

def hash_c(titulo, url):
    return hashlib.sha256(f"{titulo}{url}".encode()).hexdigest()

def ya_existe(h):
    return len(sb.table("contenidos").select("id").eq("hash_contenido", h).execute().data) > 0

def get_fuente_id(nombre):
    # ID hardcodeado para fuentes originales, lookup para las nuevas
    if "id" in FUENTES.get(nombre, {}):
        return FUENTES[nombre]["id"]
    res = sb.table("fuentes").select("id").eq("nombre", nombre).execute()
    return res.data[0]["id"] if res.data else None

def fecha_desde_url(url):
    """Extrae fecha del slug tipo /20240729130317.html — más fiable que el HTML"""
    import re
    m = re.search(r'/(\d{4})(\d{2})(\d{2})\d+\.html', url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except:
            pass
    return None

def guardar(titulo, resumen, url, fuente_id, subcategoria, img_url=None, fecha=None):
    h = hash_c(titulo, url)
    if ya_existe(h):
        return False
    sb.table("contenidos").insert({
        "municipio_id":      MUNICIPIO_ID,
        "fuente_id":         fuente_id,
        "categoria":         "noticia",
        "subcategoria":      subcategoria,
        "etiquetas":         ["algete", subcategoria],
        "titulo":            titulo,
        "resumen":           resumen[:400],
        "cuerpo":            resumen[:400],
        "url_original":      url,
        "url_imagen":        img_url,
        "fecha_publicacion": (fecha or datetime.now(timezone.utc)).isoformat(),
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
        return " ".join(w.capitalize() for w in slug.replace("-"," ").split())
    except:
        return None

async def extraer_og(client, url, base=""):
    """Extrae og:image y og:description de un artículo"""
    try:
        r = await client.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        img = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            img = og_img["content"]
            if img.startswith("/"):
                img = base + img
        desc = None
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            desc = og_desc["content"][:400]
        return img, desc
    except:
        return None, None

# ── SCRAPERS ─────────────────────────────────────────────────

async def scrape_aytoalgete(client):
    nuevos = 0
    fid = get_fuente_id("Ayuntamiento de Algete")
    BASE = "https://aytoalgete.es"
    try:
        r = await client.get(BASE, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "lxml")
        for item in soup.select(".news"):
            for a in item.select("a"):
                href = a.get("href","")
                if "com_k2" not in href or "view=item" not in href:
                    continue
                txt = a.get_text(strip=True)
                titulo = txt if (txt and len(txt) > 8 and txt.lower() not in ["leer más","leer mas","ver"]) else slug_to_titulo(href)
                if not titulo:
                    continue
                full_url = href if href.startswith("http") else BASE + href
                p = item.select_one("p, .catItemIntroText")
                resumen = p.get_text(strip=True)[:300] if p else titulo
                img, extracto = await extraer_og(client, full_url, BASE)
                if extracto and len(extracto) > len(resumen):
                    resumen = extracto
                sub = clasificar(titulo + " " + resumen)
                if guardar(titulo, resumen, full_url, fid, sub, img):
                    nuevos += 1
                break
    except Exception as e:
        log.error(f"  Error Aytoalgete: {e}")
    return nuevos

async def scrape_soydealgete(client):
    nuevos = 0
    fid = get_fuente_id("SoyDeAlgete")
    BASE = "https://www.soydemadrid.com"
    try:
        r = await client.get(f"{BASE}/noticias-algete/", headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "lxml")
        for art in soup.select("article")[:20]:
            for a in art.select("a"):
                txt = a.get_text(strip=True)
                if len(txt) < 20 or any(x in txt.lower() for x in ["leer","ver más","compartir"]):
                    continue
                if "algete" not in (art.get_text() + txt).lower():
                    continue
                url = a.get("href","")
                if not url.startswith("http"):
                    url = BASE + url
                p = art.select_one("p, .excerpt")
                resumen = p.get_text(strip=True)[:300] if p else txt
                img, extracto = await extraer_og(client, url, BASE)
                if extracto and len(extracto) > len(resumen):
                    resumen = extracto
                sub = clasificar(txt + " " + resumen)
                if guardar(txt, resumen, url, fid, sub, img):
                    nuevos += 1
                break
    except Exception as e:
        log.error(f"  Error SoyDeAlgete: {e}")
    return nuevos

async def scrape_rss(client, nombre, rss_url, filtro="algete"):
    nuevos = 0
    fid = get_fuente_id(nombre)
    if not fid:
        return 0
    try:
        r = await client.get(rss_url, headers=HEADERS, timeout=15)
        root = ET.fromstring(r.text)
        ns = {"media": "http://search.yahoo.com/mrss/"}
        for item in root.findall(".//item")[:30]:
            titulo = (item.findtext("title","")).strip()
            link   = (item.findtext("link","")).strip()
            desc   = (item.findtext("description","")).strip()
            pub    = (item.findtext("pubDate","")).strip()
            if filtro and filtro not in (titulo + desc).lower():
                continue
            if not titulo or not link:
                continue
            desc_soup = BeautifulSoup(desc, "lxml")
            resumen = desc_soup.get_text(strip=True)[:400] or titulo
            img = None
            media = item.find("media:content", ns)
            if media is not None:
                img = media.get("url")
            if not img:
                img_tag = desc_soup.find("img")
                if img_tag:
                    img = img_tag.get("src")
            fecha = None
            if pub:
                try:
                    fecha = parsedate_to_datetime(pub).replace(tzinfo=timezone.utc)
                except:
                    pass
            sub = clasificar(titulo + " " + resumen)
            # Priorizar fecha del slug de URL (más fiable que el HTML)
            fecha_slug = fecha_desde_url(link)
            if fecha_slug:
                fecha = fecha_slug
            if guardar(titulo, resumen, link, fid, sub, img, fecha):
                nuevos += 1
    except Exception as e:
        log.error(f"  Error RSS {nombre}: {e}")
    return nuevos

async def scrape_web(client, nombre, url):
    nuevos = 0
    fid = get_fuente_id(nombre)
    if not fid:
        return 0
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for art in soup.select("article, .post, .entry")[:20]:
            h = art.select_one("h2 a, h3 a, h1 a, .entry-title a, .post-title a")
            if not h:
                continue
            titulo = h.get_text(strip=True)
            link = h.get("href","")
            if not link.startswith("http"):
                link = base + link
            if "algete" not in (titulo + art.get_text()).lower():
                continue
            p = art.select_one("p, .excerpt, .entry-summary")
            resumen = p.get_text(strip=True)[:400] if p else titulo
            img_el = art.select_one("img")
            img = img_el.get("src") if img_el else None
            fecha = None
            t = art.select_one("time")
            if t and t.get("datetime"):
                try:
                    fecha = datetime.fromisoformat(t["datetime"].replace("Z","+00:00"))
                except:
                    pass
            sub = clasificar(titulo + " " + resumen)
            # Priorizar fecha del slug de URL (más fiable que el HTML)
            fecha_slug = fecha_desde_url(link)
            if fecha_slug:
                fecha = fecha_slug
            if guardar(titulo, resumen, link, fid, sub, img, fecha):
                nuevos += 1
    except Exception as e:
        log.error(f"  Error web {nombre}: {e}")
    return nuevos

# ── MAIN ─────────────────────────────────────────────────────

async def main():
    log.info("═══ InfoLocal Scraper v2 ═══")
    total = 0

    async with httpx.AsyncClient(follow_redirects=True) as client:
        log.info("── Ayuntamiento de Algete ──")
        total += await scrape_aytoalgete(client)

        log.info("── SoyDeAlgete ──")
        total += await scrape_soydealgete(client)

        log.info("── Madrid Norte 24h (RSS) ──")
        total += await scrape_rss(client, "Madrid Norte 24h", "https://www.madridnorte24horas.com/rss/")

        log.info("── Madrid 24 Horas ──")
        total += await scrape_web(client, "Madrid 24 Horas", "https://www.madrid24horas.com/tags/algete/")

        log.info("── Madrid Es Noticia ──")
        total += await scrape_web(client, "Madrid Es Noticia", "https://www.madridesnoticia.es/secciones/municipios/algete/")

        log.info("── El Diario de Madrid ──")
        total += await scrape_web(client, "El Diario de Madrid", "https://www.eldiariodemadrid.es/tags/algete/")

    sb.table("scraping_log").insert({
        "fuente_id":         FUENTES["Ayuntamiento de Algete"]["id"],
        "items_encontrados": total,
        "items_nuevos":      total,
        "estado":            "ok"
    }).execute()

    log.info(f"✅ {total} noticias nuevas")

asyncio.run(main())
