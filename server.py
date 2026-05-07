# -------------------------------------------------------
# SensoRAG - Flask Web Server
# -------------------------------------------------------
# Serves the frontend and exposes API endpoints:
#   POST /upload            - accept and ingest a sensor datasheet file
#   POST /query             - run a RAG query against ingested documents
#   GET  /documents         - list all currently indexed documents
#   DELETE /documents/:name - remove a single document
#   POST /preload           - load sample datasheets
#   POST /clear             - remove all documents
#
# API key handling:
#   The /query endpoint accepts an optional API key from the frontend
#   via the X-API-Key header. This lets users bring their own Anthropic
#   key so the app operator doesn't pay for API calls. If no key is
#   provided, falls back to the server's ANTHROPIC_API_KEY env var.
# -------------------------------------------------------

import os
import shutil

# load .env file before anything else (sets ANTHROPIC_API_KEY etc.)
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
# secure_filename: sanitizes uploaded filenames to prevent path traversal
from werkzeug.utils import secure_filename

from rag_engine import RAGEngine

# -------------------------------------------------------
# Configuration
# -------------------------------------------------------
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
# ChromaDB persistent storage directory (SQLite-backed vector index)
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chroma_db')
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv', 'tsv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

# -------------------------------------------------------
# App Initialization
# -------------------------------------------------------
app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# single RAG engine instance shared across all requests
rag = RAGEngine(upload_dir=UPLOAD_DIR, persist_dir=CHROMA_DIR)


def allowed_file(filename):
    """Check if a filename has an allowed extension (pdf, txt, csv, tsv)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------------------------------------------
# Routes
# -------------------------------------------------------

@app.route('/')
def index():
    """Serve the main single-page frontend."""
    return app.send_static_file('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """
    Handle file upload: validate, save to disk, and ingest into RAG index.
    Returns JSON with success message and updated document list.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': f'Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    success = rag.ingest_document(filepath, filename)
    if success:
        return jsonify({'message': f'Indexed: {filename}', 'documents': rag.get_document_list()})
    return jsonify({'error': 'Could not extract text from file'}), 400


@app.route('/query', methods=['POST'])
def query():
    """
    Handle a RAG query: retrieve relevant chunks, generate an answer.

    Accepts an optional X-API-Key header from the frontend. If present,
    that key is used for the Claude API call instead of the server's
    env var. This is the "bring your own key" pattern.
    """
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': 'No query provided'}), 400

    query_text = data['query']
    top_k = data.get('top_k', 5)

    # check for user-provided API key in the request header
    api_key = request.headers.get('X-API-Key')

    results = rag.retrieve(query_text, top_k=top_k)
    if not results:
        return jsonify({
            'answer': 'No relevant results found. Upload sensor datasheets first.',
            'sources': []
        })

    # pass the user's API key (or None to fall back to env var)
    response = rag.generate_answer(query_text, results, api_key=api_key)
    return jsonify(response)


@app.route('/documents', methods=['GET'])
def documents():
    """Return the list of all ingested documents and their chunk counts."""
    return jsonify({'documents': rag.get_document_list()})


@app.route('/preload', methods=['POST'])
def preload():
    """Copy all sample datasheets into uploads/ and ingest them."""
    if not os.path.isdir(SAMPLES_DIR):
        return jsonify({'error': 'No sample datasheets found'}), 404
    loaded = []
    for fname in os.listdir(SAMPLES_DIR):
        fpath = os.path.join(SAMPLES_DIR, fname)
        if os.path.isfile(fpath) and allowed_file(fname):
            dest = os.path.join(UPLOAD_DIR, fname)
            shutil.copy2(fpath, dest)
            if rag.ingest_document(dest, fname):
                loaded.append(fname)
    return jsonify({
        'message': f'Loaded {len(loaded)} sample datasheet(s)',
        'documents': rag.get_document_list()
    })


@app.route('/documents/<filename>', methods=['DELETE'])
def delete_document(filename):
    """Remove a single document from the index and delete its file."""
    filename = secure_filename(filename)
    if not rag.remove_document(filename):
        return jsonify({'error': 'Document not found'}), 404
    filepath = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(filepath):
        os.remove(filepath)
    return jsonify({'message': f'Removed: {filename}', 'documents': rag.get_document_list()})


@app.route('/clear', methods=['POST'])
def clear():
    """Remove all ingested documents and delete uploaded files."""
    # clear uploaded files from disk
    for fname in os.listdir(UPLOAD_DIR):
        fpath = os.path.join(UPLOAD_DIR, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)
    # clear the ChromaDB collection and in-memory state
    rag.clear_all()
    return jsonify({'message': 'Cleared', 'documents': []})


# -------------------------------------------------------
# Entry Point
# -------------------------------------------------------
if __name__ == '__main__':
    # ensure uploads directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    print("[sensoRAG] Starting server at http://localhost:5000")
    app.run(debug=True, port=5000)
