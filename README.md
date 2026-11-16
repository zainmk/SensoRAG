# SensoRAG

https://senso-rag.vercel.app/

RAG-based sensor/transducer selection tool. Upload sensor datasheets (PDF, TXT, CSV, TSV), then query with natural language to find the best components for your use case.

https://github.com/user-attachments/assets/ff0477ae-bc8a-4fca-92e1-4c1ff89a0779


### Purpose
RAG (Retrieval Augmented Generation) tools can be used to directly relate LLM analysis to provide data inputs and provide one of those inputs as a 'suggested' output, that the user can trust. In the context of transducer selection given a mechatronic ask, the user provides several data sheets related specifically to transducers that could be used. These data sheest are the controlled inputs the user provides to the LLM model to be trained on. After embedding/training, the model can query an 'ask', and output a specific file for that 'ask', therefore catering LLM output's to a user-defined domain. The LLM also provides a contextual 'justification' for that output. The final sensor suggested can then be further verified 'mathematically' after the RAG has provided it's NLP-contextual analysis and output.
> The goal here is to use LLM's to bridge the reasoning/explanation between the technical considerations of the transducers available, with the actual logic required to enact it realistically. RAG is an effective way to also control the output - so the LLM only responds with respect to the data sheets that are relevant.

### Stack
- Flask; to host the application in a full framework
- Python; Used as general language and interpereting environment
- all-MiniLM-L6-v2; ChromaDB's built-in embedding model, run locally with ONNX Runtime. Converts each datasheet chunk and the query into a 384-number vector, so they can be compared by meaning rather than exact keywords
- ChromaDB: Database designed specifically to hold vector embeddings, for purposes such as these. Each search loads the data sheets into a temporary in-memory collection, finds the chunks closest to the query, then discards them.

### Anthropic API Key
Makes use of the 'Anthropic API key' that can be provided/stored on the frontend. Used to power the final LLM output response.
Without any API key, the app still functions — it returns the raw retrieved chunks without LLM synthesis.
