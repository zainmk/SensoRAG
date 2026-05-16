import io
import os
from pathlib import Path

os.environ['HOME'] = '/tmp'

import chromadb
import pdfplumber


class RAGEngine:
    def __init__(self):
        self.chroma_client = chromadb.EphemeralClient()
        self.collection = self.chroma_client.get_or_create_collection(
            name="sensor_chunks",
            metadata={"hnsw:space": "cosine"}
        )
        self._id_counter = 0

    def extract_text(self, file_bytes, filename):
        ext = Path(filename).suffix.lower()
        if ext == '.pdf':
            text = ""
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        if ext in ('.txt', '.csv', '.tsv'):
            return file_bytes.decode('utf-8', errors='ignore')
        return ""

    def chunk_text(self, text, chunk_size=300, overlap=75):
        words = text.split()
        chunks = []
        step = max(1, chunk_size - overlap)
        for i in range(0, len(words), step):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def ingest(self, file_bytes, filename):
        text = self.extract_text(file_bytes, filename)
        if not text.strip():
            return False
        chunks = self.chunk_text(text)
        if not chunks:
            return False
        ids = [f"chunk_{self._id_counter + i}" for i in range(len(chunks))]
        self._id_counter += len(chunks)
        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=[{"source": filename} for _ in chunks]
        )
        return True

    def retrieve(self, query, top_k=5):
        if self.collection.count() == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        output = []
        for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
            score = round(1.0 - dist, 4)
            if score > 0.01:
                output.append({'chunk': doc, 'source': meta['source'], 'score': score})
        return output

    def generate_answer(self, query, results, api_key=None):
        context = "\n\n".join([f"[Source: {r['source']}]\n{r['chunk']}" for r in results])
        try:
            import anthropic
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
            return {
                'answer': (
                    "**No API key configured** - showing raw retrieval matches below. "
                    "Enter your Anthropic API key above, or set ANTHROPIC_API_KEY in .env "
                    "for AI-generated answers."
                ),
                'sources': results
            }
