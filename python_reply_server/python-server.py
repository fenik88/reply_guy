from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import requests

# ✅ Put your key in an env var instead of hardcoding:
# export GEMINI_API_KEY="AIza..."
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# ✅ Use a model that exists for your key (from ListModels). Default is fast + stable.
# You can override with: export GEMINI_MODEL="models/gemini-2.0-flash-001"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-flash-latest").strip()

class ReplyGeneratorHandler(BaseHTTPRequestHandler):

    def _set_cors_headers(self):
        """Set CORS headers for all responses"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '3600')

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == '/generate':
            try:
                # Read request body
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                tweet_text = data.get('tweetText', '')
                images = data.get('images', [])
                tone = data.get('tone', 'bullish')

                print(f"\n🐦 Received tweet: {tweet_text[:50]}...")
                print(f"🎯 Tone: {tone}")

                # Generate reply using Gemini API
                reply = self.generate_reply(tweet_text, images, tone)

                print(f"✅ Generated reply: {reply}\n")

                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._set_cors_headers()
                self.end_headers()

                response = {
                    'success': True,
                    'reply': reply
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))

            except Exception as e:
                print(f"❌ Error: {str(e)}\n")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self._set_cors_headers()
                self.end_headers()

                response = {
                    'success': False,
                    'error': str(e)
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/' or self.path == '/status':
            # Serve status page
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(self.get_status_page().encode('utf-8'))

        elif self.path == '/health':
            # Health check endpoint
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            response = {'status': 'ok', 'message': 'Server is running'}
            self.wfile.write(json.dumps(response).encode('utf-8'))
            print("🏥 Health check received")
        else:
            self.send_response(404)
            self.end_headers()

    def generate_reply(self, tweet_text, images, tone):
        """Generate reply using Google Gemini API"""

        if not GEMINI_API_KEY:
            raise Exception("⚠️ GEMINI_API_KEY is not set. Run: export GEMINI_API_KEY='AIza...' and restart the server")

        prompt = f"""You are an expert at crafting viral X (Twitter) replies for crypto and Polymarket content.

TWEET TO REPLY TO:
"{tweet_text}"
"""

        if images and len(images) > 0:
            prompt += f"\n\nThe tweet contains {len(images)} image(s). Consider visual context in your reply."

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

Return ONLY the reply text, nothing else. No quotes, no preamble, just the reply."""

        # Call Google Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

        response = requests.post(
            url,
            headers={
                'Content-Type': 'application/json',
            },
            json={
                'contents': [{
                    'parts': [{
                        'text': prompt
                    }]
                }],
                'generationConfig': {
                    'temperature': 0.9,
                    'maxOutputTokens': 150,
                    'topP': 0.95,
                }
            },
            timeout=30
        )

        if response.status_code != 200:
            raise Exception(f"Gemini API Error: {response.status_code} - {response.text}")

        data = response.json()

        # Extract reply from Gemini response
        try:
            reply = data['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Gemini response: {str(e)}")

        # Clean up the reply
        reply = reply.strip('"').strip("'").strip()

        return reply

    def get_status_page(self):
        """Return HTML status page"""
        api_status = "✅ Gemini API Key Configured" if GEMINI_API_KEY else "⚠️ API Key Missing"
        status_color = "#10b981" if GEMINI_API_KEY else "#f59e0b"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>X Reply Generator - Server</title>
    <meta charset="UTF-8">
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
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 50px;
            border-radius: 20px;
            border: 2px solid rgba(255,255,255,0.2);
            max-width: 600px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            font-size: 42px;
            margin-bottom: 20px;
        }}
        .status {{
            background: #10b981;
            padding: 15px 30px;
            border-radius: 12px;
            display: inline-block;
            font-weight: 700;
            margin: 25px 0;
            font-size: 18px;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.8; }}
        }}
        .api-status {{
            background: {status_color};
            padding: 12px 20px;
            border-radius: 10px;
            display: inline-block;
            font-weight: 600;
            margin: 15px 0;
            font-size: 14px;
        }}
        .model-info {{
            background: rgba(255,255,255,0.1);
            padding: 12px 20px;
            border-radius: 10px;
            margin: 15px 0;
            font-size: 14px;
        }}
        .free-badge {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            padding: 8px 16px;
            border-radius: 8px;
            display: inline-block;
            font-weight: 700;
            margin: 10px 0;
            font-size: 13px;
        }}
        .url {{
            background: rgba(255,255,255,0.15);
            padding: 20px;
            border-radius: 12px;
            font-family: 'Courier New', monospace;
            font-size: 20px;
            margin: 25px 0;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        .instructions {{
            text-align: left;
            margin-top: 35px;
        }}
        .instructions h3 {{
            margin-bottom: 15px;
            font-size: 20px;
        }}
        .step {{
            background: rgba(255,255,255,0.08);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 12px;
            border-left: 4px solid #10b981;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✨ X Reply Generator</h1>
        <div class="status">🟢 SERVER ONLINE</div>
        <div class="api-status">{api_status}</div>
        <div class="free-badge">🆓 100% FREE API</div>
        <div class="model-info">🤖 Model: {GEMINI_MODEL}</div>
        <div class="url">http://localhost:8765</div>

        <div class="instructions">
            <h3>📋 Status</h3>
            <div class="step">✅ Server running on port 8765</div>
            <div class="step">🔌 Extension can connect</div>
            <div class="step">🐦 Ready to generate replies</div>
            <div class="step">💚 FREE - No credit card needed!</div>
            <div class="step">⚡ 1500 requests/day limit</div>
        </div>
    </div>
</body>
</html>
"""

    def log_message(self, format, *args):
        # Suppress default logging, we have custom prints
        return

def run_server(port=8765):
    if not GEMINI_API_KEY:
        print("\n" + "=" * 60)
        print("⚠️  WARNING: GEMINI API KEY NOT SET")
        print("=" * 60)
        print("\nSet your FREE Gemini API key as an environment variable and restart:")
        print("\n  export GEMINI_API_KEY=\"AIza...\"")
        print("\nOptional: choose a model you have access to:")
        print("  export GEMINI_MODEL=\"models/gemini-2.0-flash-001\"")
        print("\nThen run:")
        print("  python3 python-server.py")
        print("\n" + "=" * 60 + "\n")

    server_address = ('', port)
    httpd = HTTPServer(server_address, ReplyGeneratorHandler)

    print("=" * 60)
    print("✨ X Reply Generator Server (Google Gemini)")
    print("=" * 60)
    print(f"\n🚀 Server running on http://localhost:{port}")
    print(f"📊 Status page: http://localhost:{port}/")
    print(f"🤖 Model: {GEMINI_MODEL}")
    print(f"💚 Free tier: 1500 requests/day")
    print(f"\n💡 Keep this window open while using the extension")
    print(f"🛑 Press Ctrl+C to stop the server\n")
    print("=" * 60)
    print("\nWaiting for requests from extension...")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
        httpd.shutdown()

if __name__ == '__main__':
    run_server()