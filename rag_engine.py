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
        import json
        context = "\n\n".join([f"[Source: {r['source']}]\n{r['chunk']}" for r in results])
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
            prompt = (
                "You are a sensor selection assistant. Based on the following sensor datasheet excerpts, "
                "answer the user's query.\n\n"
                f"--- SENSOR DATASHEET EXCERPTS ---\n{context}\n\n"
                f"--- USER QUERY ---\n{query}\n\n"
                "Respond with a JSON object containing exactly these two fields:\n"
                "{\n"
                '  "recommendation": "2-3 sentences explaining why the top-matching datasheet best answers the query. Reference specific technical values (range, precision, tolerance, etc.) from it.",\n'
                '  "assumptions": ["short assumption 1", "short assumption 2"]\n'
                "}\n"
                "Include 2-4 assumptions about the use case. Return only valid JSON with no markdown fences."
            )
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = json.loads(response.content[0].text.strip())
            return {
                'recommendation': parsed.get('recommendation', ''),
                'assumptions': parsed.get('assumptions', []),
                'sources': results
            }
        except Exception:
            return {
                'recommendation': None,
                'assumptions': [],
                'sources': results
            }
