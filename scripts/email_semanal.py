# ============================================================
#  LocalInfo — Email semanal de noticias
#  Ejecutar: cada lunes a las 8:00h via Render Cron
# ============================================================
import os, json, logging, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("localinfo.email")

SUPABASE_URL  = os.environ["SUPABASE_URL"]
SUPABASE_KEY  = os.environ["SUPABASE_KEY"]
RESEND_KEY    = os.environ["RESEND_KEY"]
FROM_EMAIL    = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
FROM_NAME     = "LocalInfo · Algete"
MUNICIPIO_ID  = "1400c5a4-452f-4764-9ec2-6d10898ad285"
APP_URL       = "https://localinfo.es"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_noticias_semana():
    """Obtiene las mejores noticias de los últimos 7 días"""
    hace_7_dias = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    res = sb.table("contenidos")\
        .select("titulo, resumen, url_original, url_imagen, categoria, subcategoria, fecha_publicacion, fuente_id")\
        .eq("municipio_id", MUNICIPIO_ID)\
        .eq("activo", True)\
        .gte("fecha_publicacion", hace_7_dias)\
        .order("fecha_publicacion", desc=True)\
        .limit(10)\
        .execute()
    return res.data

def get_suscriptores():
    """Obtiene todos los emails suscritos"""
    res = sb.table("suscriptores")\
        .select("email, nombre")\
        .eq("activo", True)\
        .execute()
    return res.data

def pill_color(categoria):
    colores = {
        "evento":  "#3B82F6",
        "ayuda":   "#22C55E",
        "tramite": "#A855F7",
        "alerta":  "#E12828",
        "noticia": "#666666",
    }
    return colores.get(categoria, "#666666")

def pill_label(categoria, subcategoria):
    labels = {
        "evento": "Evento", "ayuda": "Ayuda", "tramite": "Trámite",
        "alerta": "Alerta", "noticia": "Noticia",
        "cultura": "Cultura", "deporte": "Deporte", "politica": "Política",
        "educacion": "Educación", "seguridad": "Seguridad",
    }
    return labels.get(subcategoria) or labels.get(categoria, "Local")

def fecha_bonita(iso):
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return d.strftime("%-d de %B").replace(
            "January","enero").replace("February","febrero").replace("March","marzo")\
            .replace("April","abril").replace("May","mayo").replace("June","junio")\
            .replace("July","julio").replace("August","agosto").replace("September","septiembre")\
            .replace("October","octubre").replace("November","noviembre").replace("December","diciembre")
    except:
        return str(iso)[:10]

def generar_html(noticias, nombre="vecino"):
    semana = datetime.now().strftime("%-d de %B de %Y").replace(
        "January","enero").replace("February","febrero").replace("March","marzo")\
        .replace("April","abril").replace("May","mayo").replace("June","junio")\
        .replace("July","julio").replace("August","agosto").replace("September","septiembre")\
        .replace("October","octubre").replace("November","noviembre").replace("December","diciembre")

    noticias_html = ""
    for n in noticias[:8]:
        img_html = ""
        if n.get("url_imagen"):
            img_html = f'<img src="{n["url_imagen"]}" style="width:100%;height:200px;object-fit:cover;display:block;border-radius:6px 6px 0 0" alt="">'

        color = pill_color(n.get("categoria","noticia"))
        label = pill_label(n.get("categoria","noticia"), n.get("subcategoria",""))
        fecha = fecha_bonita(n.get("fecha_publicacion",""))
        resumen = (n.get("resumen") or "")[:180]
        url = n.get("url_original", APP_URL)

        noticias_html += f"""
        <div style="background:#1a1a1a;border-radius:8px;margin-bottom:16px;overflow:hidden;border:1px solid #2a2a2a">
          {img_html}
          <div style="padding:16px">
            <span style="background:{color};color:white;font-size:11px;font-weight:700;padding:3px 8px;border-radius:3px;letter-spacing:.04em">{label}</span>
            <h3 style="color:#ffffff;font-size:16px;font-weight:700;margin:10px 0 6px;line-height:1.35">{n['titulo']}</h3>
            <p style="color:#aaaaaa;font-size:13px;line-height:1.6;margin:0 0 12px">{resumen}{'...' if len(resumen)==180 else ''}</p>
            <div style="display:flex;align-items:center;justify-content:space-between">
              <span style="color:#666;font-size:11px">{fecha}</span>
              <a href="{url}" style="color:#E12828;font-size:12px;font-weight:600;text-decoration:none">Leer más →</a>
            </div>
          </div>
        </div>"""

    if not noticias:
        noticias_html = '<p style="color:#aaa;text-align:center;padding:2rem">Sin novedades esta semana</p>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LocalInfo · Novedades de Algete</title></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:Arial,sans-serif">
  <div style="max-width:600px;margin:0 auto;padding:20px">

    <!-- HEADER -->
    <div style="text-align:center;padding:32px 0 24px">
      <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:-1px">
        local<span style="color:#E12828">info</span><span style="color:#ffffff">.</span>
      </div>
      <div style="color:#666;font-size:13px;margin-top:6px">📍 Algete · Semana del {semana}</div>
    </div>

    <!-- SALUDO -->
    <div style="background:#161616;border-radius:8px;padding:20px;margin-bottom:24px;border-left:3px solid #E12828">
      <p style="color:#ffffff;font-size:15px;margin:0;line-height:1.6">
        Hola <strong>{nombre}</strong> 👋<br>
        Esto es lo más importante que ha pasado en <strong>Algete</strong> esta semana.
      </p>
    </div>

    <!-- NOTICIAS -->
    {noticias_html}

    <!-- CTA -->
    <div style="text-align:center;padding:24px 0">
      <a href="{APP_URL}" style="background:#E12828;color:white;padding:14px 32px;border-radius:4px;text-decoration:none;font-weight:700;font-size:14px;display:inline-block">
        Ver todas las noticias →
      </a>
    </div>

    <!-- FOOTER -->
    <div style="border-top:1px solid #1a1a1a;padding:20px 0;text-align:center">
      <p style="color:#444;font-size:11px;margin:0;line-height:1.8">
        LocalInfo · La actualidad de Algete<br>
        <a href="{APP_URL}" style="color:#666;text-decoration:none">localinfo.es</a>
        · <a href="{APP_URL}/baja?email={{email}}" style="color:#666;text-decoration:none">Darse de baja</a>
      </p>
    </div>

  </div>
</body>
</html>"""

def enviar_email(destinatario_email, destinatario_nombre, html):
    payload = json.dumps({
        "from":    f"{FROM_NAME} <{FROM_EMAIL}>",
        "to":      [destinatario_email],
        "subject": f"📍 Algete esta semana — {datetime.now().strftime('%-d de %B')}",
        "html":    html
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_KEY}",
            "Content-Type": "application/json"
        }
    )
    try:
        res = urllib.request.urlopen(req, timeout=15)
        data = json.loads(res.read())
        return data.get("id")
    except urllib.error.HTTPError as e:
        log.error(f"Resend error {e.code}: {e.read().decode()[:200]}")
        return None

def main():
    log.info("═══ LocalInfo · Email semanal ═══")

    noticias = get_noticias_semana()
    log.info(f"Noticias de la semana: {len(noticias)}")

    suscriptores = get_suscriptores()
    log.info(f"Suscriptores activos: {len(suscriptores)}")

    if not noticias:
        log.warning("Sin noticias esta semana — email cancelado")
        return

    enviados = errores = 0
    for s in suscriptores:
        html = generar_html(noticias, s.get("nombre", "vecino"))
        email_id = enviar_email(s["email"], s.get("nombre",""), html)
        if email_id:
            log.info(f"  ✓ {s['email']}")
            enviados += 1
        else:
            log.error(f"  ✗ {s['email']}")
            errores += 1

    log.info(f"\n✅ {enviados} enviados · {errores} errores")

if __name__ == "__main__":
    main()
