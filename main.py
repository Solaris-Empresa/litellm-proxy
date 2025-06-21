#!/usr/bin/env python3
# litellm_proxy_custom.py - Proxy customizado para interceptar tool calls
import json
import requests
from flask import Flask, request, jsonify
import openai
from litellm import completion
import os

app = Flask(__name__)

# Configurações
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FASTAPI_RAG_URL = "https://solarisempresa-iasolaris.hf.space/search"
openai.api_key = OPENAI_API_KEY

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
