# ============================================================
#  InfoLocal — API REST (FastAPI)
#  Arrancar: uvicorn main:app --reload --port 8000
# ============================================================

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from pydantic import BaseModel
from typing import Optional
import os
import urllib.request
import json as json_lib

# ── Config ──────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://iktkiskmqshsxnwqhvvp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdGtpc2ttcXNoc3hud3FodnZwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODk0ODA3MiwiZXhwIjoyMTA0NTI0MDcyfQ.tkwqXK1QWEkCwlYxfstufbx1OCCMvoFXwDRZQeCTUh8")

sb  = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI(title="InfoLocal API", version="1.0")

# ── CORS — permite llamadas desde el frontend ────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Modelos ──────────────────────────────────────────────────
class PerfilUpdate(BaseModel):
    nombre:        Optional[str]  = None
    intereses:     Optional[list] = None
    notif_diaria:  Optional[bool] = None
    notif_alertas: Optional[bool] = None
    notif_ayudas:  Optional[bool] = None


# ════════════════════════════════════════════════════════════
#  MUNICIPIOS
# ════════════════════════════════════════════════════════════
@app.get("/municipios")
def listar_municipios():
    """Lista todos los municipios disponibles en InfoLocal."""
    res = sb.table("municipios").select("*").eq("activo", True).execute()
    return res.data


@app.get("/municipios/{codigo_ine}")
def get_municipio(codigo_ine: str):
    """Detalle de un municipio por código INE."""
    res = sb.table("municipios").select("*").eq("codigo_ine", codigo_ine).single().execute()
    if not res.data:
        raise HTTPException(404, "Municipio no encontrado")
    return res.data


# ════════════════════════════════════════════════════════════
#  CONTENIDOS — FEED PRINCIPAL
# ════════════════════════════════════════════════════════════
@app.get("/feed/{municipio_id}")
def feed(
    municipio_id: str,
    categoria:    Optional[str] = Query(None),
    subcategoria: Optional[str] = Query(None),
    limite:       int           = Query(20, ge=1, le=50),
    offset:       int           = Query(0, ge=0),
):
    """
    Feed de contenidos de un municipio.
    Filtra por categoría o subcategoría si se pasan como parámetros.
    """
    query = sb.table("contenidos")\
        .select("id, titulo, resumen, categoria, subcategoria, etiquetas, url_original, url_imagen, fecha_publicacion, fecha_inicio, fecha_fin, lugar, es_gratuito, es_alerta, fuente_id")\
        .eq("municipio_id", municipio_id)\
        .eq("activo", True)\
        .order("es_alerta", desc=True)\
        .order("fecha_publicacion", desc=True)\
        .range(offset, offset + limite - 1)

    if categoria:
        query = query.eq("categoria", categoria)
    if subcategoria:
        query = query.eq("subcategoria", subcategoria)

    res = query.execute()
    return {"total": len(res.data), "items": res.data}


@app.get("/contenidos/{contenido_id}")
def get_contenido(contenido_id: str):
    """Detalle completo de un contenido."""
    res = sb.table("contenidos")\
        .select("*, fuentes(nombre, url)")\
        .eq("id", contenido_id)\
        .single()\
        .execute()
    if not res.data:
        raise HTTPException(404, "Contenido no encontrado")
    return res.data


# ════════════════════════════════════════════════════════════
#  ALERTAS URGENTES
# ════════════════════════════════════════════════════════════
@app.get("/alertas/{municipio_id}")
def alertas(municipio_id: str):
    """Alertas activas de un municipio (cortes, emergencias, avisos)."""
    # Alertas de la tabla dedicada
    res_alertas = sb.table("alertas")\
        .select("*")\
        .eq("municipio_id", municipio_id)\
        .eq("activa", True)\
        .execute()

    # También contenidos marcados como alerta
    res_contenidos = sb.table("contenidos")\
        .select("id, titulo, resumen, created_at")\
        .eq("municipio_id", municipio_id)\
        .eq("es_alerta", True)\
        .eq("activo", True)\
        .execute()

    return {
        "alertas":     res_alertas.data,
        "contenidos":  res_contenidos.data,
        "total":       len(res_alertas.data) + len(res_contenidos.data)
    }


# ════════════════════════════════════════════════════════════
#  AGENDA — EVENTOS
# ════════════════════════════════════════════════════════════
@app.get("/agenda/{municipio_id}")
def agenda(
    municipio_id: str,
    limite: int = Query(20, ge=1, le=50)
):
    """Próximos eventos del municipio ordenados por fecha."""
    res = sb.table("contenidos")\
        .select("id, titulo, resumen, fecha_inicio, fecha_fin, lugar, es_gratuito, url_original")\
        .eq("municipio_id", municipio_id)\
        .eq("categoria", "evento")\
        .eq("activo", True)\
        .order("fecha_inicio")\
        .limit(limite)\
        .execute()
    return {"items": res.data}


# ════════════════════════════════════════════════════════════
#  AYUDAS Y SUBVENCIONES
# ════════════════════════════════════════════════════════════
@app.get("/ayudas/{municipio_id}")
def ayudas(municipio_id: str):
    """Ayudas y subvenciones activas, ordenadas por fecha límite."""
    res = sb.table("contenidos")\
        .select("id, titulo, resumen, fecha_fin, url_original, etiquetas")\
        .eq("municipio_id", municipio_id)\
        .eq("categoria", "ayuda")\
        .eq("activo", True)\
        .order("fecha_fin")\
        .execute()
    return {"items": res.data}


# ════════════════════════════════════════════════════════════
#  BÚSQUEDA DE TEXTO
# ════════════════════════════════════════════════════════════
@app.get("/buscar/{municipio_id}")
def buscar(
    municipio_id: str,
    q:      str = Query(..., min_length=2),
    limite: int = Query(10, ge=1, le=20)
):
    """Búsqueda full-text en títulos y resúmenes."""
    res = sb.table("contenidos")\
        .select("id, titulo, resumen, categoria, subcategoria, fecha_publicacion, url_original")\
        .eq("municipio_id", municipio_id)\
        .eq("activo", True)\
        .ilike("titulo", f"%{q}%")\
        .limit(limite)\
        .execute()
    return {"query": q, "total": len(res.data), "items": res.data}


# ════════════════════════════════════════════════════════════
#  PERFIL DE USUARIO
# ════════════════════════════════════════════════════════════
@app.get("/perfil/{usuario_id}")
def get_perfil(usuario_id: str):
    """Obtiene el perfil e intereses del usuario."""
    res = sb.table("perfiles")\
        .select("*, municipios(nombre, provincia)")\
        .eq("id", usuario_id)\
        .single()\
        .execute()
    if not res.data:
        raise HTTPException(404, "Perfil no encontrado")
    return res.data


@app.patch("/perfil/{usuario_id}")
def update_perfil(usuario_id: str, perfil: PerfilUpdate):
    """Actualiza intereses y preferencias del usuario."""
    datos = {k: v for k, v in perfil.dict().items() if v is not None}
    if not datos:
        raise HTTPException(400, "No hay datos que actualizar")
    res = sb.table("perfiles").update(datos).eq("id", usuario_id).execute()
    return {"ok": True, "updated": datos}


# ════════════════════════════════════════════════════════════
#  ESTADÍSTICAS — para el dashboard del ayuntamiento
# ════════════════════════════════════════════════════════════
@app.get("/stats/{municipio_id}")
def stats(municipio_id: str):
    """Estadísticas básicas del municipio para dashboard."""
    total    = sb.table("contenidos").select("id", count="exact").eq("municipio_id", municipio_id).eq("activo", True).execute()
    noticias = sb.table("contenidos").select("id", count="exact").eq("municipio_id", municipio_id).eq("categoria", "noticia").execute()
    eventos  = sb.table("contenidos").select("id", count="exact").eq("municipio_id", municipio_id).eq("categoria", "evento").execute()
    ayudas   = sb.table("contenidos").select("id", count="exact").eq("municipio_id", municipio_id).eq("categoria", "ayuda").execute()
    log      = sb.table("scraping_log").select("*").order("ejecutado_at", desc=True).limit(1).execute()

    return {
        "total_contenidos": total.count,
        "noticias":         noticias.count,
        "eventos":          eventos.count,
        "ayudas":           ayudas.count,
        "ultimo_scraping":  log.data[0] if log.data else None,
    }


# ════════════════════════════════════════════════════════════
#  ASISTENTE IA
# ════════════════════════════════════════════════════════════
class PreguntaIA(BaseModel):
    pregunta: str
    municipio_id: str

@app.post("/chat/{municipio_id}")
def chat(municipio_id: str, body: PreguntaIA):
    """Asistente IA que responde sobre el municipio usando datos reales."""
    pregunta = body.pregunta.strip()
    if not pregunta:
        raise HTTPException(400, "Pregunta vacía")

    # 1. Buscar contenidos relevantes en Supabase
    resultados = sb.table("contenidos")        .select("titulo, resumen, categoria, subcategoria, fecha_publicacion, url_original")        .eq("municipio_id", municipio_id)        .eq("activo", True)        .ilike("titulo", f"%{pregunta.split()[0]}%")        .order("fecha_publicacion", desc=True)        .limit(5)        .execute().data

    # Si no hay resultados con la primera palabra, buscar más amplio
    if not resultados:
        resultados = sb.table("contenidos")            .select("titulo, resumen, categoria, subcategoria, fecha_publicacion, url_original")            .eq("municipio_id", municipio_id)            .eq("activo", True)            .order("fecha_publicacion", desc=True)            .limit(8)            .execute().data

    # 2. Construir contexto para la IA
    contexto = "\n".join([
        f"- [{r['categoria'].upper()}] {r['titulo']}: {r['resumen'] or ''} (Fecha: {str(r['fecha_publicacion'])[:10]})"
        for r in resultados
    ])

    prompt = f"""Eres el asistente de InfoLocal, una app de noticias locales para vecinos de Algete (Madrid).
Responde de forma breve, amigable y útil en español. Máximo 3 frases.
Si la información está en el contexto, úsala. Si no, di que no tienes esa información disponible ahora mismo.

PREGUNTA DEL VECINO: {pregunta}

CONTENIDOS RECIENTES DE ALGETE:
{contexto}

RESPUESTA:"""

    # 3. Llamar a Gemini
    gemini_key = os.getenv("GEMINI_KEY", "")
    if not gemini_key:
        # Fallback sin IA — respuesta basada solo en búsqueda
        if resultados:
            resp = f"He encontrado {len(resultados)} resultado(s) relacionado(s): {resultados[0]['titulo']}."
        else:
            resp = "No tengo información sobre eso en Algete en este momento."
        return {"respuesta": resp, "fuentes": resultados[:3]}

    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={gemini_key}"
        data = json_lib.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 200}
        }).encode()
        req = urllib.request.Request(gemini_url, data=data, headers={"Content-Type": "application/json"})
        res = urllib.request.urlopen(req, timeout=20)
        respuesta = json_lib.loads(res.read())["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        respuesta = f"He encontrado {len(resultados)} resultado(s) sobre tu pregunta en Algete." if resultados else "No tengo información sobre eso ahora mismo."

    return {
        "respuesta": respuesta,
        "fuentes": resultados[:3]
    }


# ════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ════════════════════════════════════════════════════════════
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0", "app": "InfoLocal"}

@app.get("/ping")
def ping():
    """Keep-alive endpoint — llamado cada 10 min desde el frontend"""
    return {"pong": True}
