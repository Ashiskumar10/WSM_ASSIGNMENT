"""Flask application for the WSM Text Search Engine project."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from backend.document_loader import load_corpus
from backend.search_engine import SearchEngine

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend" / "templates"),
    static_folder=str(BASE_DIR / "frontend" / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB per request
app.config["JSON_SORT_KEYS"] = False

engine = SearchEngine()


def rebuild_index() -> None:
    documents = load_corpus(DATA_DIR)
    engine.build(documents)


# The included sample corpus is indexed automatically on application startup.
rebuild_index()


@app.get("/")
def homepage():
    return render_template("index.html")


@app.post("/search")
def search():
    payload = request.get_json(silent=True) or request.form
    query = str(payload.get("query", "")).strip()
    mode = str(payload.get("mode", "ranked")).lower()
    phonetic = str(payload.get("phonetic", "false")).lower() in {"true", "1", "yes", "on"}
    spell_correct = str(payload.get("spell_correct", "true")).lower() in {"true", "1", "yes", "on"}

    if not query:
        return jsonify({"error": "Enter a search query."}), 400

    started = perf_counter()
    try:
        response = engine.search(query=query, mode=mode, phonetic=phonetic, spell_correct=spell_correct)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    response["query"] = query
    response["execution_time_ms"] = round((perf_counter() - started) * 1000, 2)
    return jsonify(response)


@app.post("/upload")
def upload():
    incoming = request.files.getlist("files")
    if not incoming:
        single = request.files.get("file")
        incoming = [single] if single else []
    incoming = [item for item in incoming if item and item.filename]
    if not incoming:
        return jsonify({"error": "Choose at least one TXT file to upload."}), 400

    saved_files: list[str] = []
    rejected_files: list[str] = []
    for item in incoming:
        original_name = item.filename or ""
        safe_name = secure_filename(original_name)
        if not safe_name or Path(safe_name).suffix.lower() != ".txt":
            rejected_files.append(original_name or "Unnamed file")
            continue

        destination = UPLOAD_DIR / safe_name
        if destination.exists():
            stem = destination.stem
            suffix = destination.suffix
            counter = 2
            while (UPLOAD_DIR / f"{stem}_{counter}{suffix}").exists():
                counter += 1
            destination = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
        item.save(destination)
        saved_files.append(destination.name)

    if not saved_files:
        return jsonify({
            "error": "No valid .txt files were uploaded.",
            "rejected_files": rejected_files,
        }), 400

    rebuild_index()
    return jsonify({
        "message": f"Indexed {len(saved_files)} TXT file(s) successfully.",
        "uploaded_files": saved_files,
        "rejected_files": rejected_files,
        "stats": engine.stats(),
    })


@app.get("/stats")
def stats():
    return jsonify(engine.stats())


@app.get("/health")
def health():
    return jsonify({"status": "ok", "indexed": engine.indexed, "documents": engine.index.document_count})


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "Upload too large. The maximum request size is 16 MB."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
