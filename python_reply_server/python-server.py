from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import time
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()

PORT = int(os.getenv("PORT", "8765"))

class ReplyGeneratorHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
            self.wfile.write(self.get_status_page().encode("utf-8"))
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

        self.send_response(404)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path != "/generate":
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()
            return

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

    def generate_reply(self, tweet_text, images, tone):
        if not GROQ_API_KEY:
            raise Exception("GROQ_API_KEY is not set. Run: export GROQ_API_KEY='...' and restart server.")
        if not tweet_text:
            raise Exception("tweetText is empty")

        prompt = f"""You are an expert at crafting viral X (Twitter) replies for crypto and Polymarket content.

TWEET TO REPLY TO:
"{tweet_text}"
"""
        if images:
            prompt += f"\nThe tweet contains {len(images)} image(s). Consider visual context."

        prompt += f"""

TONE: {tone}

Generate ONE perfect reply. The reply must:
- Be SHORT (1-2 sentences max, preferably 1)
- Use the {tone} tone
- Create EMOTION (curiosity, excitement, FOMO, intrigue, controversy)
- AVOID: emojis, dots, brackets, parentheses, these words: profit, bet, money, gamble, betting, gambling, wager, odds
- Focus on: prediction markets, forecasting, events, outcomes, market wisdom, collective intelligence
- HOOK the reader to reply back or follow for more
- Be conversational and natural
- Use questions strategically to boost engagement

Return ONLY the reply text, nothing else.
"""

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

        # Simple retry for 429 rate limits (free plan caps)
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

    def get_status_page(self):
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>X Reply Generator - Groq</title></head>
<body style="font-family: -apple-system, system-ui; padding: 24px;">
<h1>✨ X Reply Generator</h1>
<p><b>Provider:</b> Groq (OpenAI-compatible)</p>
<p><b>Model:</b> {GROQ_MODEL}</p>
<p><b>Base URL:</b> {GROQ_BASE_URL}</p>
<p><b>API key:</b> {"set" if GROQ_API_KEY else "missing"}</p>
<p><b>Endpoints:</b> <code>/health</code> <code>/generate</code></p>
</body></html>"""

    def log_message(self, format, *args):
        return

def run_server():
    print(f"🚀 Server: http://localhost:{PORT}")
    print(f"🤖 Groq model: {GROQ_MODEL}")
    HTTPServer(("", PORT), ReplyGeneratorHandler).serve_forever()

if __name__ == "__main__":
    run_server()