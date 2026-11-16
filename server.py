import os

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from rag_engine import RAGEngine

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv', 'tsv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Short descriptors for the bundled samples, taken from each datasheet's own
# overview. Files without an entry are listed by filename alone.
SAMPLE_DESCRIPTIONS = {
    '6370_spec.pdf': 'Wireless temperature station - platinum thermistor',
    '6382_SS.pdf': 'Wireless temperature + humidity station',
    '7210_Spec_Sheet_Rev_B_Web.pdf': 'Wi-Fi air quality sensor - laser particulate (PM)',
    '86002255.pdf': 'LoRaWAN dry contact sensor - switch / button state',
    '86002256.pdf': 'LoRaWAN ultrasonic level sensor - 0.5 to 10 m',
    '86002266.pdf': 'LoRaWAN leak detection sensor - probe or rope',
    '86002267.pdf': 'LoRaWAN temperature and temperature/humidity sensors',
    '86002277.pdf': 'LoRaWAN movement sensor - accelerometer, tilt, motion',
    'HCSR04.pdf': 'Ultrasonic rangefinder module - 2 to 400 cm',
    'MPC023-24-001-T _ NEMA 23 Spring Applied Power-Off Brake.pdf':
        'NEMA 23 power-off brake - actuator, not a sensor',
    'RB00010_Single_Push_Button_User_Guide.pdf': 'LoRaWAN single push button sensor',
    'TR-Electronic-Pressure-Regulator-Datasheet.pdf':
        'Electro-pneumatic pressure regulator - actuator, not a sensor',
    'document.pdf': 'Limitorque MX/QX smart electric valve actuators',
    'fluid-trac-3-wire-level-sensor-ft-an2.pdf':
        'Ultrasonic liquid level sensor - 3-wire voltage output',
    'magnetic-sensing-solutions-sp-an1.pdf':
        'Magnetic speed/position sensors - variable reluctance, Hall effect',
    'p51-pressure-sensor-p51-ds-rev-1-10-722.pdf':
        'P51 pressure sensor - absolute, sealed and gauge',
    'tulc-combination-sensor-tulc-an.pdf':
        'DEF tank combination sensor - temperature, level, concentration',
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sample_files():
    """Names of the bundled sample datasheets, sorted."""
    if not os.path.isdir(SAMPLES_DIR):
        return []
    return sorted(f for f in os.listdir(SAMPLES_DIR)
                  if os.path.isfile(os.path.join(SAMPLES_DIR, f)) and allowed_file(f))


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/samples')
def samples():
    return jsonify([{'name': f,
                     'about': SAMPLE_DESCRIPTIONS.get(f, ''),
                     'size': os.path.getsize(os.path.join(SAMPLES_DIR, f))}
                    for f in sample_files()])


@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query', '').strip()
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    with RAGEngine() as rag:
        for file in request.files.getlist('files[]'):
            if file and file.filename and allowed_file(file.filename):
                rag.ingest(file.read(), secure_filename(file.filename))

        if request.form.get('samples') == 'true':
            for fname in sample_files():
                with open(os.path.join(SAMPLES_DIR, fname), 'rb') as f:
                    rag.ingest(f.read(), fname)

        results = rag.retrieve(query)
        if not results:
            return jsonify({'recommendation': None, 'assumptions': [], 'sources': [],
                            'message': 'No relevant results found. Attach datasheets or include sample data.'})

        return jsonify(rag.generate_answer(query, results, api_key=request.headers.get('X-API-Key')))


if __name__ == '__main__':
    print("[sensoRAG] Starting server at http://localhost:5000")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
