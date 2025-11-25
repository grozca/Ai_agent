import requests

url = "http://localhost:11434/api/generate"
payload = {
    "model": "llama3",
    "prompt": "Di solo: Hola desde la API de Ollama",
    "stream": False,
}

print("Llamando a Ollama...")
resp = requests.post(url, json=payload, timeout=60)
print("Status code:", resp.status_code)
print("Respuesta (primeros 500 chars):")
print(resp.text[:500])
