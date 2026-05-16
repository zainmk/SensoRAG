import os

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from rag_engine import RAGEngine

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv', 'tsv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/test')
def test():
    return 'hello world'


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query', '').strip()
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    rag = RAGEngine()

    for file in request.files.getlist('files[]'):
        if file and file.filename and allowed_file(file.filename):
            rag.ingest(file.read(), secure_filename(file.filename))

    if request.form.get('samples') == 'true' and os.path.isdir(SAMPLES_DIR):
        for fname in os.listdir(SAMPLES_DIR):
            fpath = os.path.join(SAMPLES_DIR, fname)
            if os.path.isfile(fpath) and allowed_file(fname):
                with open(fpath, 'rb') as f:
                    rag.ingest(f.read(), fname)

    results = rag.retrieve(query)
    if not results:
        return jsonify({'answer': 'No relevant results found. Attach datasheets or include sample data.', 'sources': []})

    return jsonify(rag.generate_answer(query, results, api_key=request.headers.get('X-API-Key')))


if __name__ == '__main__':
    print("[sensoRAG] Starting server at http://localhost:5000")
    app.run(debug=True, port=5000)
