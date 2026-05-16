# [SensoRAG](https://senso-rag.vercel.app/)

RAG-based sensor/transducer selection tool. Upload sensor datasheets (PDF, TXT, CSV, TSV), then query with natural language to find the best components for your use case.

### purpose
RAG tools can be used to directly relate LLM analysis to providede data inputs and provide one of those inputs as a 'suggested' output, that the user can trust. In the context of transducer selection given a mechatronic ask, the user provides several data sheets related specifically to transducers that could be used. These data sheest are the controlled inputs the user provides to the LLM model to be trained on. After embedding/training, the model can query an 'ask', and output a specific file for that 'ask', therefore catering LLM output's to a user-defined domain. The LLM also provides a contextual 'justification' for that output. The final sensor suggested can then be further verified 'mathematically' after the RAG has provided it's NLP-contextual analysis and output.

# tools
Flask, Python, FastEmbed, ChromaDB

# api keys
Makes use of the 'anthropic api key' that can be provided/stored on the frontend. Used to power the final LLM output response.
Without any API key, the app still functions — it returns the raw retrieved chunks without LLM synthesis.




##### refs
UI DESIGN [https://dribbble.com/shots/26816864-Nova-1-Identity]
