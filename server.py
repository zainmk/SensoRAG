import os

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from rag_engine import RAGEngine

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv', 'tsv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

rag = RAGEngine()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': f'Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    filename = secure_filename(file.filename)
    if rag.ingest(file.read(), filename):
        return jsonify({'message': f'Indexed: {filename}', 'documents': rag.get_document_list()})
    return jsonify({'error': 'Could not extract text from file'}), 400


@app.route('/query', methods=['POST'])
def query():
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': 'No query provided'}), 400
    query_text = data['query']
    top_k = data.get('top_k', 5)
    api_key = request.headers.get('X-API-Key')
    results = rag.retrieve(query_text, top_k=top_k)
    if not results:
        return jsonify({'answer': 'No relevant results found. Upload sensor datasheets first.', 'sources': []})
    return jsonify(rag.generate_answer(query_text, results, api_key=api_key))


@app.route('/documents', methods=['GET', 'DELETE'])
def documents():
    if request.method == 'DELETE':
        rag.clear_all()
        return jsonify({'message': 'Cleared', 'documents': []})
    return jsonify({'documents': rag.get_document_list()})



def load_samples():
    if not os.path.isdir(SAMPLES_DIR) or rag.collection.count() > 0:
        return
    for fname in os.listdir(SAMPLES_DIR):
        fpath = os.path.join(SAMPLES_DIR, fname)
        if os.path.isfile(fpath) and allowed_file(fname):
            with open(fpath, 'rb') as f:
                rag.ingest(f.read(), fname)
    print(f"[sensoRAG] Loaded {len(rag.documents)} sample datasheet(s)")


if __name__ == '__main__':
    load_samples()
    print("[sensoRAG] Starting server at http://localhost:5000")
    app.run(debug=True, port=5000)
