import requests

MODEL_NAME = "models/gemini-1.5-flash-001"  # example — use the one from ListModels

key = "AIzaSyCfvnMI83QLaclgqDIqz4LtgxpGeuhntgg"
r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={key}", timeout=30)
r.raise_for_status()
models = r.json().get("models", [])

usable = [
    (m["name"], m.get("supportedGenerationMethods", []))
    for m in models
    if "generateContent" in m.get("supportedGenerationMethods", [])
]

for name, methods in usable:
    print(name, methods)