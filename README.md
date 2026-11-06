# Findly — Text Search Engine

Flask-based modular text search engine with the original frontend preserved.

## Run locally (Windows / macOS / Linux)

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Deploy online (GitHub + Render)

**GitHub Pages cannot run Python/Flask backend code.** Keep this repository on GitHub and deploy
the whole Flask application to Render (or another Python web host):

1. Push this project to GitHub (include `app.py`, `backend/`, `frontend/`, `data/`, `requirements.txt`, `Procfile`, `render.yaml`).
2. In Render choose **New → Web Service**, connect this GitHub repository.
3. Render detects `render.yaml`; use build command `pip install -r requirements.txt` and start command `gunicorn app:app`.
4. Deploy. Open the Render URL; the same frontend and `/search`, `/upload`, `/stats` backend routes run together.

## Important upload persistence note
On free/ephemeral hosting, uploaded TXT files may disappear after a restart/redeploy. The bundled demo corpus is indexed at startup.
For permanent user uploads, configure a persistent disk or external storage on your host.

## Project modules
- `backend/document_loader.py` — document loading
- `backend/tokenizer.py` — tokenization
- `backend/text_normalizer.py` — normalization/case folding
- `backend/inverted_index.py` — inverted index
- `backend/query_processor.py` — query processing
- `backend/wildcard_processor.py` — wildcard handling
- `backend/search_engine.py` — engine integration
- `frontend/templates/index.html` — UI
- `frontend/static/` — CSS and JavaScript
