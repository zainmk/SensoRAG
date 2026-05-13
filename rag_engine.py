# -------------------------------------------------------
# SensoRAG - RAG Engine (FastEmbed + ChromaDB)
# -------------------------------------------------------
# Core retrieval-augmented generation logic:
#   1. Extracts text from uploaded sensor datasheets (PDF/TXT/CSV)
#   2. Splits text into overlapping chunks for granular matching
#   3. Stores chunks as dense vector embeddings in ChromaDB
#   4. Retrieves top-k relevant chunks via semantic similarity
#   5. Generates a natural-language answer via Claude API
#
# -------------------------------------------------------

import os
from pathlib import Path
import pdfplumber

# chromadb: vector database with built-in FastEmbed support
# - stores document chunks as dense embeddings
# - handles similarity search internally
# - persists to disk via SQLite so data survives server restarts
import chromadb


class RAGEngine:
    """
    Minimal RAG engine using FastEmbed embeddings + ChromaDB retrieval
    and optional LLM generation via Claude API.
    """

    def __init__(self, upload_dir='uploads', persist_dir='chroma_db'):
        # directory where uploaded files are stored on disk
        self.upload_dir = upload_dir

        # list of document metadata dicts: {filename, chunk_count}
        self.documents = []

        # --- ChromaDB setup ---
        # PersistentClient stores vectors on disk (SQLite-backed) so the
        # index survives server restarts without re-ingesting all documents.
        # The default embedding function uses FastEmbed's BAAI/bge-small-en-v1.5
        # model (~30MB, 384-dim vectors) which slightly outperforms the popular
        # all-MiniLM-L6-v2 on retrieval benchmarks.
        self.chroma_client = chromadb.PersistentClient(path=persist_dir)

        # get_or_create_collection: reuses existing collection if present,
        # creates a new one if not. "sensor_chunks" is the single collection
        # where all datasheet chunks live.
        self.collection = self.chroma_client.get_or_create_collection(
            name="sensor_chunks",
            # metadata tells ChromaDB to rank results by cosine similarity
            # (as opposed to L2 distance or inner product)
            metadata={"hnsw:space": "cosine"}
        )

        # running counter for generating unique chunk IDs within ChromaDB
        # start from the current collection size so IDs don't collide
        # after a server restart with persisted data
        self._id_counter = self.collection.count()

    # ----- text extraction -----

    def extract_text_from_pdf(self, filepath):
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                # extract_text() returns None if page has no readable text
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    def extract_text(self, filepath):
        """
        Dispatch text extraction based on file extension.
        Supports: .pdf (via pdfplumber), .txt/.csv/.tsv (raw read).
        Returns extracted text as a single string.
        """
        ext = Path(filepath).suffix.lower()
        if ext == '.pdf':
            return self.extract_text_from_pdf(filepath)
        if ext in ('.txt', '.csv', '.tsv'):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        return ""

    # ----- chunking -----

    def chunk_text(self, text, chunk_size=300, overlap=75):
        """
        Split text into overlapping chunks for better retrieval granularity.

        Why overlap? Without it, a relevant sentence that spans a chunk
        boundary gets split across two chunks, and neither chunk alone
        scores high enough to be retrieved. A 75-word overlap ensures
        boundary content appears in at least one complete chunk.

        chunk_size=300 words: roughly one paragraph — large enough to
        capture a sensor's key specs, small enough for precise retrieval.
        """
        words = text.split()
        chunks = []
        step = max(1, chunk_size - overlap)
        for i in range(0, len(words), step):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    # ----- document ingestion -----

    def ingest(self, filepath, filename):
        """
        Full document ingestion pipeline:
        1. Extract raw text from the file
        2. Split into overlapping chunks
        3. Add chunks to ChromaDB (embedding happens automatically)
        Returns True on success, False if no text could be extracted.

        ChromaDB's .add() method automatically embeds each chunk using
        the collection's embedding function (FastEmbed by default) and
        stores both the vector and the original text.
        """
        text = self.extract_text(filepath)
        if not text.strip():
            return False

        chunks = self.chunk_text(text)
        if not chunks:
            return False

        # store document metadata for the frontend document list
        self.documents.append({'filename': filename, 'chunk_count': len(chunks)})

        # generate unique IDs for each chunk (ChromaDB requires string IDs)
        ids = [f"chunk_{self._id_counter + i}" for i in range(len(chunks))]
        self._id_counter += len(chunks)

        # metadatas: attach the source filename to each chunk so we can
        # display which datasheet a result came from
        metadatas = [{"source": filename} for _ in chunks]

        # .add() triggers FastEmbed to convert each chunk into a 384-dim
        # dense vector, then stores it in the HNSW index for fast retrieval
        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )

        return True

    # ----- retrieval -----

    def retrieve(self, query, top_k=5):
        """
        Retrieve the top-k most relevant text chunks for a given query.

        How this works under the hood:
        1. FastEmbed embeds the query into the same 384-dim vector space
        2. ChromaDB's HNSW index finds the nearest chunk vectors by cosine similarity
        3. Results come back with distances (lower = more similar for cosine)

        Returns list of dicts: {chunk, source, score} sorted by relevance.
        """
        # guard: can't retrieve if no documents have been indexed yet
        if self.collection.count() == 0:
            return []

        # .query() embeds the query string and searches the vector index
        # include=["documents", "metadatas", "distances"] tells ChromaDB
        # what to return alongside the matched IDs
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        # unpack ChromaDB's nested list format (outer list = per-query batch)
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]

        output = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB returns cosine *distance* (0 = identical, 2 = opposite)
            # convert to a similarity score (1 = identical, 0 = orthogonal)
            score = round(1.0 - dist, 4)
            # filter out very low relevance results
            if score > 0.01:
                output.append({
                    'chunk': doc,
                    'source': meta['source'],
                    'score': score
                })

        return output

    # ----- LLM answer generation -----

    def generate_answer(self, query, results, api_key=None):
        """
        Generate a natural-language answer using Claude API.
        Sends the retrieved chunks as context along with the user's query.

        api_key: if provided (from frontend), uses that key instead of
        the server's ANTHROPIC_API_KEY env var. This lets users bring
        their own key so the app operator doesn't pay for API calls.

        Falls back to raw retrieval results if no API key is available.
        """
        # build a context block from all retrieved chunks with source attribution
        context = "\n\n".join(
            [f"[Source: {r['source']}]\n{r['chunk']}" for r in results]
        )

        try:
            import anthropic

            # if user provided their own key, use it; otherwise fall back
            # to the ANTHROPIC_API_KEY environment variable
            client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

            prompt = (
                "You are a sensor selection assistant. Based on the following sensor datasheet excerpts, "
                "answer the user's query. Reference specific technical specifications (precision, uncertainty, "
                "tolerance, range, etc.) and name the source document for each recommendation.\n\n"
                f"--- SENSOR DATASHEET EXCERPTS ---\n{context}\n\n"
                f"--- USER QUERY ---\n{query}\n\n"
                "Provide a concise, factual answer. Cite specific values from the datasheets."
            )

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return {'answer': response.content[0].text, 'sources': results}

        except Exception:
            # fallback: return the raw retrieved chunks without LLM synthesis
            fallback = (
                "**No API key configured** - showing raw retrieval matches below. "
                "Enter your Anthropic API key above, or set ANTHROPIC_API_KEY in .env "
                "for AI-generated answers."
            )
            return {'answer': fallback, 'sources': results}

    # ----- document management -----

    def remove_document(self, filename):
        """
        Remove a single document and its chunks from the ChromaDB collection.
        Uses metadata filtering to find all chunks belonging to this file.
        """
        doc = next((d for d in self.documents if d['filename'] == filename), None)
        if not doc:
            return False

        # ChromaDB supports filtering by metadata — find all chunks from this file
        # and delete them by their IDs
        matching = self.collection.get(
            where={"source": filename},
            include=[]
        )
        if matching['ids']:
            self.collection.delete(ids=matching['ids'])

        # remove from our document list
        self.documents = [d for d in self.documents if d['filename'] != filename]
        return True

    def clear_all(self):
        """
        Remove all chunks from the ChromaDB collection.
        Deletes and recreates the collection for a clean slate.
        """
        self.chroma_client.delete_collection("sensor_chunks")
        self.collection = self.chroma_client.get_or_create_collection(
            name="sensor_chunks",
            metadata={"hnsw:space": "cosine"}
        )
        self.documents = []
        self._id_counter = 0

    def get_document_list(self):
        """Return metadata for all ingested documents (for frontend display)."""
        return [{'filename': d['filename'], 'chunks': d['chunk_count']} for d in self.documents]
