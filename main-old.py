#!/usr/bin/env python3
# litellm_proxy_custom.py - Proxy customizado para interceptar tool calls
import json
import requests
from flask import Flask, request, jsonify, abort, Response
import openai
from litellm import completion
import os
from uuid import uuid4

app = Flask(__name__)

# Configurações
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FASTAPI_RAG_URL = "https://solarisempresa-iasolaris.hf.space/search"
OPENAI_BASE_URL = "https://api.openai.com/v1"
openai.api_key = OPENAI_API_KEY

# In-memory storage for assistants
assistants_store = {}

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """Intercepta chamadas para OpenAI e processa tool calls"""
    try:
        data = request.get_json()
        # Primeira chamada para OpenAI via LiteLLM
        response = completion(
            model=data.get('model', 'gpt-4'),
            messages=data.get('messages', []),
            tools=data.get('tools', []),
            tool_choice=data.get('tool_choice', 'auto'),
            **{k: v for k, v in data.items() if k not in ['model', 'messages', 'tools', 'tool_choice']}
        )
        # Verifica se há tool calls
        if hasattr(response, 'choices') and response.choices[0].message.tool_calls:
            tool_calls = response.choices[0].message.tool_calls
            # Processa cada tool call
            tool_results = []
            for tool_call in tool_calls:
                if tool_call.function.name == "buscar_documentos":
                    # Chama nosso FastAPI
                    function_args = json.loads(tool_call.function.arguments)
                    rag_response = call_fastapi_rag(function_args.get('consulta', ''))
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": json.dumps(rag_response)
                    })
            # Se temos resultados de tools, faz segunda chamada
            if tool_results:
                # Adiciona tool calls à conversa
                messages = data.get('messages', [])
                messages.append(response.choices[0].message.dict())
                messages.extend(tool_results)
                # Segunda chamada para gerar resposta final
                final_response = completion(
                    model=data.get('model', 'gpt-4'),
                    messages=messages,
                    **{k: v for k, v in data.items() if k not in ['model', 'messages', 'tools', 'tool_choice']}
                )
                return jsonify(final_response.dict())
        # Se não há tool calls, retorna resposta original
        return jsonify(response.dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def call_fastapi_rag(consulta):
    """Chama o FastAPI RAG"""
    try:
        response = requests.post(
            FASTAPI_RAG_URL,
            json={"consulta": consulta},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Erro ao chamar RAG: {str(e)}"}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "ok"}), 200

@app.route('/v1/assistants', methods=['GET', 'POST'])
def assistants():
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    if request.method == 'GET':
        params = request.args.to_dict()
        resp = requests.get(f"{OPENAI_BASE_URL}/assistants", headers=headers, params=params)
        return (resp.content, resp.status_code, resp.headers.items())
    elif request.method == 'POST':
        resp = requests.post(f"{OPENAI_BASE_URL}/assistants", headers=headers, json=request.get_json())
        return (resp.content, resp.status_code, resp.headers.items())

@app.route('/v1/assistants/<assistant_id>', methods=['GET', 'DELETE'])
def assistant_detail(assistant_id):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    if request.method == 'GET':
        resp = requests.get(f"{OPENAI_BASE_URL}/assistants/{assistant_id}", headers=headers)
        return (resp.content, resp.status_code, resp.headers.items())
    elif request.method == 'DELETE':
        resp = requests.delete(f"{OPENAI_BASE_URL}/assistants/{assistant_id}", headers=headers)
        return (resp.content, resp.status_code, resp.headers.items())

@app.route('/v1/<path:path>', methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def proxy_openai(path):
    # Do not proxy /v1/chat/completions (custom logic)
    if path == "chat/completions":
        abort(404)
    method = request.method
    url = f"{OPENAI_BASE_URL}/{path}"
    headers = dict(request.headers)
    headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    headers["Host"] = "api.openai.com"
    # Remove headers that should not be forwarded
    headers.pop("Content-Length", None)
    headers.pop("Transfer-Encoding", None)
    # Forward query params
    params = request.args.to_dict()
    # Forward body if present
    data = request.get_data() if request.data else None
    resp = requests.request(method, url, headers=headers, params=params, data=data, stream=True)
    excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
    response_headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
    return Response(resp.content, resp.status_code, response_headers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
