from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from litellm.proxy.proxy_server import app as litellm_app
from litellm import completion
import json
import requests
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FASTAPI_RAG_URL = "https://solarisempresa-iasolaris.hf.space/search"

main_app = FastAPI()

@main_app.post("/v1/chat/completions")
async def custom_chat_completions(request: Request):
    data = await request.json()
    response = completion(
        model=data.get('model', 'gpt-4'),
        messages=data.get('messages', []),
        tools=data.get('tools', []),
        tool_choice=data.get('tool_choice', 'auto'),
        **{k: v for k, v in data.items() if k not in ['model', 'messages', 'tools', 'tool_choice']}
    )
    # Tool call logic (RAG)
    if hasattr(response, 'choices') and response.choices[0].message.tool_calls:
        tool_calls = response.choices[0].message.tool_calls
        tool_results = []
        for tool_call in tool_calls:
            if tool_call.function.name == "buscar_documentos":
                function_args = json.loads(tool_call.function.arguments)
                rag_response = call_fastapi_rag(function_args.get('consulta', ''))
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(rag_response)
                })
        if tool_results:
            messages = data.get('messages', [])
            messages.append(response.choices[0].message.dict())
            messages.extend(tool_results)
            final_response = completion(
                model=data.get('model', 'gpt-4'),
                messages=messages,
                **{k: v for k, v in data.items() if k not in ['model', 'messages', 'tools', 'tool_choice']}
            )
            return JSONResponse(final_response.dict())
    return JSONResponse(response.dict())

def call_fastapi_rag(consulta):
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

# Mount LiteLLM's proxy for all other endpoints
main_app.mount("/", litellm_app)

# To run: uvicorn app_litellm_proxy:main_app --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:main_app", host="0.0.0.0", port=8000, reload=True)