# SensoRAG

RAG-based sensor/transducer selection tool. Upload sensor datasheets (PDF, TXT, CSV, TSV), then query with natural language to find the best components for your use case.

## Architecture

```
User Query
    |
    v
[FastEmbed] -- embeds query into 384-dim dense vector
    |
    v
[ChromaDB]  -- finds nearest chunk vectors by cosine similarity
    |
    v
[Top-K Chunks] -- most relevant datasheet excerpts
    |
    v
[Claude API] -- generates a natural-language answer citing sources
    |
    v
Response (answer + source excerpts + relevance scores)
```

## Design Decisions

### Embedding: FastEmbed (ONNX Runtime) over TF-IDF and sentence-transformers

The original implementation used **TF-IDF** (scikit-learn) for retrieval. TF-IDF represents text as sparse word-frequency vectors and matches queries by keyword overlap. This fails for conceptual queries — "sensors for a line following robot" would not match a datasheet describing "optical reflectance detection" because they share no keywords, even though they describe the same thing.

Dense embedding models solve this by mapping text into a continuous vector space where semantically similar content lands near each other, regardless of the specific words used.

Two options were considered:

| | sentence-transformers (PyTorch) | FastEmbed (ONNX Runtime) |
|---|---|---|
| **Runtime** | PyTorch (~800MB - 2GB) | ONNX Runtime (~30-50MB) |
| **Model size** | ~80MB (float32) | ~30-50MB (int8 quantized) |
| **Total footprint** | ~1-2GB | ~70-100MB |
| **Quality** | Excellent | Equivalent (same architectures, ONNX-converted) |
| **Use case** | Training + inference | Inference only |

**FastEmbed was chosen** because this application only needs inference (not training), and the ~20x smaller footprint is critical for deployment on budget hosting tiers (e.g. Render's $7/mo plan with 2GB RAM). FastEmbed uses the same model architectures (MiniLM, BGE, etc.) converted to ONNX format with INT8 quantization — same quality, fraction of the size.

The default model is **BAAI/bge-small-en-v1.5** (384 dimensions), which slightly outperforms the popular all-MiniLM-L6-v2 on retrieval benchmarks.

### Vector Store: ChromaDB over raw FAISS

ChromaDB was chosen over raw FAISS because it provides:

- **Built-in FastEmbed integration** — handles embedding automatically when adding/querying documents
- **Persistent storage** — SQLite-backed, so the vector index survives server restarts without re-ingesting
- **Metadata filtering** — attach source filenames to chunks and filter/delete by metadata
- **Single dependency** — replaces what would otherwise be FAISS + manual index management + a storage layer

### LLM: Claude API with user-provided keys

The generation step uses **Claude claude-sonnet-4-6** via the Anthropic API. To avoid the app operator paying for every user's queries, the frontend includes an optional API key input. The key is:

- Stored in the user's browser (`localStorage`) so they don't re-enter it each visit
- Sent via `X-API-Key` header on each query request
- Used for that single API call and never persisted on the server
- Falls back to the server's `ANTHROPIC_API_KEY` env var if no user key is provided

Without any API key, the app still functions — it returns the raw retrieved chunks without LLM synthesis.

### Chunking Strategy

Text is split into **300-word chunks with 75-word overlap**:

- **300 words** (~1 paragraph) is large enough to capture a sensor's key specifications in one chunk, but small enough for precise retrieval
- **75-word overlap** ensures content near chunk boundaries isn't lost — a relevant sentence spanning two chunks appears fully in at least one

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd SensoRAG

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Set a server-side API key
cp .env.example .env
# Edit .env with your Anthropic API key
# Or skip this — users can enter their own key in the UI

# 5. Run the server
python server.py
```

The app will be available at `http://localhost:5000`.

On first run, ChromaDB will download the FastEmbed model (~30MB) automatically. Subsequent starts use the cached model.

## Dependencies

| Package | Purpose |
|---|---|
| `flask` | Web framework serving the frontend and API endpoints |
| `pdfplumber` | Text extraction from uploaded PDF datasheets |
| `chromadb` | Vector database (installs `fastembed` + `onnxruntime` automatically) |
| `anthropic` | Claude API client for answer generation |
| `python-dotenv` | Loads environment variables from `.env` file |

## Project Structure

```
SensoRAG/
  rag_engine.py      # Core RAG pipeline: extraction, chunking, embedding, retrieval, generation
  server.py          # Flask web server with API endpoints
  requirements.txt   # Python dependencies
  .env.example       # Template for environment variables
  static/
    index.html       # Single-page frontend
    app.js           # Client-side logic (upload, query, API key management)
    style.css        # Styling
  samples/           # Pre-loaded sample sensor datasheets
  uploads/           # User-uploaded datasheets (created at runtime)
  chroma_db/         # ChromaDB persistent storage (created at runtime)
```
