Flask API: Exposes a POST endpoint at /v1/chat/completions.
Proxy for OpenAI: Receives a chat completion request, forwards it to OpenAI (via LiteLLM), and checks if the response includes any tool calls.
Tool Call Handling: If a tool call named "buscar_documentos" is present, it calls an external RAG API (FASTAPI_RAG_URL) with the provided query.
Tool Results: The RAG result is formatted as a tool response and injected into the conversation, then a second completion call is made to OpenAI to get the final answer.
Error Handling: Any exception is caught and returned as a JSON error.