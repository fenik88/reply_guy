from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import time
import requests
from pathlib import Path

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()

PORT = int(os.getenv("PORT", "8765"))
CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config():
    """Load user configuration from config.json"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"custom_prompt": "", "base_rules": {}, "examples": {}}

def save_config(config):
    """Save user configuration to config.json"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

class ReplyGeneratorHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "3600")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/status"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(self.get_settings_page().encode("utf-8"))
            return

        if self.path == "/health":
            ok = bool(GROQ_API_KEY)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok" if ok else "error",
                "message": "Server is running",
                "provider": "groq",
                "model": GROQ_MODEL,
                "api_key": "set" if ok else "missing"
            }).encode("utf-8"))
            return

        if self.path == "/config":
            # Get current config
            config = load_config()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(config).encode("utf-8"))
            return

        self.send_response(404)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == "/generate":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(content_length).decode("utf-8"))

                tweet_text = (data.get("tweetText") or "").strip()
                images = data.get("images") or []
                tone = (data.get("tone") or "bullish").strip()

                reply = self.generate_reply(tweet_text, images, tone)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "reply": reply}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        if self.path == "/config":
            # Update config
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                new_config = json.loads(self.rfile.read(content_length).decode("utf-8"))
                
                save_config(new_config)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Config saved"}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self._set_cors_headers()
        self.end_headers()

    def generate_reply(self, tweet_text, images, tone):
        if not GROQ_API_KEY:
            raise Exception("GROQ_API_KEY is not set. Run: export GROQ_API_KEY='...' and restart server.")
        if not tweet_text:
            raise Exception("tweetText is empty")

        # Load user's custom configuration
        config = load_config()
        custom_prompt = config.get("custom_prompt", "")

        # Build the prompt with user's custom instructions
        prompt = f"""You are an expert at crafting viral X (Twitter) replies for crypto and Polymarket content.

TWEET TO REPLY TO:
"{tweet_text}"
"""
        if images:
            prompt += f"\nThe tweet contains {len(images)} image(s). Consider visual context."

        prompt += f"\n\nTONE: {tone}\n\n"

        # Add user's custom prompt if exists
        if custom_prompt:
            prompt += f"USER'S STYLE GUIDELINES:\n{custom_prompt}\n\n"

        # Add examples if provided
        examples = config.get("examples", {}).get("good", [])
        if examples:
            prompt += "EXAMPLES OF GOOD REPLIES:\n"
            for ex in examples[:3]:  # Limit to 3 examples
                prompt += f"Tweet: \"{ex.get('tweet', '')}\"\nReply: \"{ex.get('reply', '')}\"\n\n"

        prompt += "Generate ONE perfect reply following the style guidelines above. Return ONLY the reply text, nothing else."

        url = f"{GROQ_BASE_URL}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 120,
            "top_p": 0.95,
        }

        # Simple retry for 429 rate limits
        last_text = None
        for attempt in range(3):
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            last_text = r.text
            if r.status_code == 200:
                j = r.json()
                reply = (j["choices"][0]["message"]["content"] or "").strip()
                return reply.strip('"').strip("'").strip()

            if r.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue

            raise Exception(f"Groq API Error: {r.status_code} - {r.text}")

        raise Exception(f"Groq API Error: 429 - {last_text}")

    def get_settings_page(self):
        config = load_config()
        custom_prompt = config.get("custom_prompt", "")
        
        return f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>X Reply Generator - Settings</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: white;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 42px;
            margin-bottom: 10px;
        }}
        .card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            border: 2px solid rgba(255,255,255,0.2);
        }}
        .card h2 {{
            font-size: 24px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .card p {{
            opacity: 0.9;
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        textarea {{
            width: 100%;
            min-height: 200px;
            padding: 15px;
            border-radius: 10px;
            border: 2px solid rgba(255,255,255,0.3);
            background: rgba(255,255,255,0.1);
            color: white;
            font-size: 14px;
            font-family: 'Courier New', monospace;
            line-height: 1.6;
            resize: vertical;
        }}
        textarea::placeholder {{
            color: rgba(255,255,255,0.5);
        }}
        textarea:focus {{
            outline: none;
            border-color: rgba(255,255,255,0.6);
            background: rgba(255,255,255,0.15);
        }}
        .btn {{
            background: white;
            color: #667eea;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-block;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.3);
        }}
        .btn:active {{
            transform: translateY(0);
        }}
        .status {{
            margin-top: 15px;
            padding: 15px;
            border-radius: 10px;
            display: none;
        }}
        .status.success {{
            background: rgba(16, 185, 129, 0.3);
            border: 2px solid #10b981;
            display: block;
        }}
        .status.error {{
            background: rgba(239, 68, 68, 0.3);
            border: 2px solid #ef4444;
            display: block;
        }}
        .examples {{
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }}
        .examples h3 {{
            font-size: 18px;
            margin-bottom: 15px;
        }}
        .example-item {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #10b981;
        }}
        .example-item strong {{
            display: block;
            margin-bottom: 5px;
            font-size: 12px;
            text-transform: uppercase;
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✨ X Reply Generator</h1>
            <p>Настрой свой стиль ответов</p>
        </div>

        <div class="card">
            <h2>🎨 Твой Кастомный Промпт</h2>
            <p>
                Здесь опиши КАК ты хочешь чтобы AI отвечал. Будь максимально конкретным!
                Укажи стиль, правила, что избегать, какие эмоции вызывать и тд.
            </p>
            <textarea id="customPrompt" placeholder="Например:

пиши как профессиональный трейдер на полимаркет
все твои ответы должны быть короткими но запоминающимися при этом простыми
они должны вызывать эмоции и заставить человека ответить и в лучшем случае подписаться
избегай точек слишком заумных выражений и слов по типу gamble money bet profit odds
не используй эмодзи скобки и кавычки
будь дерзким и уверенным">{custom_prompt}</textarea>

            <button class="btn" onclick="saveConfig()">💾 Сохранить Настройки</button>
            <div id="status" class="status"></div>
        </div>

        <div class="card">
            <h2>💡 Примеры Хороших Ответов</h2>
            <p>
                Можешь добавить примеры своих лучших ответов в <code>config.json</code> 
                чтобы AI учился на них (few-shot learning)
            </p>
            <div class="examples">
                <h3>Текущие примеры:</h3>
                <div id="examplesList">
                    <div class="example-item">
                        <strong>Tweet:</strong> Bitcoin just hit $100k
                        <div><strong>Reply:</strong> told you so</div>
                    </div>
                    <div class="example-item">
                        <strong>Tweet:</strong> Market is crashing
                        <div><strong>Reply:</strong> time to buy more</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📊 Статус Сервера</h2>
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px;">
                <p><strong>Провайдер:</strong> Groq</p>
                <p><strong>Модель:</strong> {GROQ_MODEL}</p>
                <p><strong>URL:</strong> http://localhost:{PORT}</p>
                <p><strong>API Key:</strong> {"✅ Установлен" if GROQ_API_KEY else "❌ Не установлен"}</p>
            </div>
        </div>
    </div>

    <script>
        async function saveConfig() {{
            const customPrompt = document.getElementById('customPrompt').value;
            const status = document.getElementById('status');
            
            try {{
                const response = await fetch('/config', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        custom_prompt: customPrompt,
                        base_rules: {{}},
                        examples: {{
                            good: [
                                {{ tweet: "Bitcoin just hit $100k", reply: "told you so" }},
                                {{ tweet: "Market is crashing", reply: "time to buy more" }},
                                {{ tweet: "Polymarket odds looking crazy", reply: "markets never lie" }}
                            ]
                        }}
                    }})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    status.className = 'status success';
                    status.textContent = '✅ Настройки сохранены! Теперь все ответы будут использовать твой стиль.';
                    setTimeout(() => {{
                        status.style.display = 'none';
                    }}, 5000);
                }} else {{
                    throw new Error(data.error);
                }}
            }} catch (error) {{
                status.className = 'status error';
                status.textContent = '❌ Ошибка: ' + error.message;
            }}
        }}
    </script>
</body>
</html>"""

    def log_message(self, format, *args):
        return

def run_server():
    print("=" * 60)
    print("✨ X Reply Generator Server")
    print("=" * 60)
    print(f"\n🚀 Server: http://localhost:{PORT}")
    print(f"⚙️  Settings: http://localhost:{PORT}/")
    print(f"🤖 Model: {GROQ_MODEL}")
    print(f"\n💡 Открой http://localhost:{PORT} чтобы настроить свой стиль!")
    print(f"🛑 Press Ctrl+C to stop\n")
    print("=" * 60)
    HTTPServer(("", PORT), ReplyGeneratorHandler).serve_forever()

if __name__ == "__main__":
    run_server()