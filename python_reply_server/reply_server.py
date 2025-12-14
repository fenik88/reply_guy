from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import requests
from urllib.parse import parse_qs

class ReplyGeneratorHandler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        if self.path == '/generate':
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            tweet_text = data.get('tweetText', '')
            images = data.get('images', [])
            tone = data.get('tone', 'bullish')
            
            print(f"\n🐦 Received tweet: {tweet_text[:50]}...")
            print(f"🎯 Tone: {tone}")
            
            try:
                # Generate reply using Claude API
                reply = self.generate_reply(tweet_text, images, tone)
                
                print(f"✅ Generated reply: {reply}")
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response = {
                    'success': True,
                    'reply': reply
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response = {
                    'success': False,
                    'error': str(e)
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
        
        elif self.path == '/':
            # Serve status page
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_status_page().encode('utf-8'))
    
    def do_GET(self):
        if self.path == '/':
            # Serve status page
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_status_page().encode('utf-8'))
        elif self.path == '/health':
            # Health check endpoint
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))
    
    def generate_reply(self, tweet_text, images, tone):
        """Generate reply using Claude API"""
        
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

        # Call Claude API
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 300,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }
        )
        
        data = response.json()
        reply = data['content'][0]['text'].strip()
        
        return reply
    
    def get_status_page(self):
        """Return HTML status page"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>X Reply Generator - Server</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
            color: white;
        }
        .container {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 40px;
            border-radius: 20px;
            border: 2px solid rgba(255,255,255,0.2);
            max-width: 600px;
            text-align: center;
        }
        h1 {
            font-size: 36px;
            margin-bottom: 16px;
        }
        .status {
            background: #10b981;
            padding: 12px 24px;
            border-radius: 10px;
            display: inline-block;
            font-weight: 600;
            margin: 20px 0;
        }
        .url {
            background: rgba(255,255,255,0.1);
            padding: 16px;
            border-radius: 10px;
            font-family: monospace;
            font-size: 18px;
            margin: 20px 0;
        }
        .instructions {
            text-align: left;
            margin-top: 30px;
        }
        .step {
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>✨ X Reply Generator</h1>
        <div class="status">🟢 Server Running</div>
        <div class="url">http://localhost:8765</div>
        <div class="instructions">
            <strong>How to use:</strong>
            <div class="step">1. Keep this server running</div>
            <div class="step">2. Install the Chrome extension</div>
            <div class="step">3. Go to X/Twitter</div>
            <div class="step">4. Click "✨ Generate" on any tweet</div>
        </div>
    </div>
</body>
</html>
"""
    
    def log_message(self, format, *args):
        # Custom logging
        return

def run_server(port=8765):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ReplyGeneratorHandler)
    
    print("=" * 60)
    print("✨ X Reply Generator Server")
    print("=" * 60)
    print(f"\n🚀 Server running on http://localhost:{port}")
    print(f"📊 Status page: http://localhost:{port}/")
    print(f"\n💡 Keep this window open while using the extension")
    print(f"🛑 Press Ctrl+C to stop the server\n")
    print("=" * 60)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
        httpd.shutdown()

if __name__ == '__main__':
    run_server()