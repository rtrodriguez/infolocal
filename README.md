# InfoLocal 🏘️

> La actualidad de tu municipio, en un vistazo.

App hiperlocal con IA que agrega noticias, eventos, ayudas y trámites
de municipios españoles y los presenta de forma personalizada.

## Stack

- **Frontend:** HTML/CSS/JS vanilla → Vercel
- **API:** Python + FastAPI → Render
- **Base de datos:** Supabase (PostgreSQL)
- **Scraping:** httpx + BeautifulSoup
- **IA:** Gemini Flash (enriquecimiento de contenidos)

## POC: Algete (Madrid)

Fuentes activas:
- aytoalgete.es (Joomla K2)
- soydemadrid.com/noticias-algete

## Despliegue

### API (Render)
1. Conecta este repo en render.com
2. Render detecta `render.yaml` automáticamente
3. Añade las variables de entorno: `SUPABASE_KEY`, `GEMINI_KEY`

### Frontend (Vercel)
1. Conecta este repo en vercel.com
2. Root directory: `frontend`
3. Deploy automático en cada push

## Estructura

```
infolocal/
├── api/
│   ├── main.py           # FastAPI — endpoints REST
│   └── requirements.txt
├── scripts/
│   └── scraper_run.py    # Scraper diario (cron 7:00h)
├── frontend/
│   └── index.html        # App web
├── render.yaml           # Config Render (API + cron)
└── README.md
```

## Variables de entorno necesarias

| Variable | Descripción |
|---|---|
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_KEY` | Service role key de Supabase |
| `GEMINI_KEY` | API key de Google AI Studio |
