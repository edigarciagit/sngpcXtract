import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
import json
import sys

PORT = 8000

class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # API Proxy Logic
        if self.path.startswith('/api/proxy'):
            self.handle_proxy()
            return

        # Default static file serving
        super().do_GET()

    def handle_proxy(self):
        try:
            # Simple query parsing for '?code=' logic
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            code = params.get('code', ['832670'])[0]
            
            target_url = f"https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/codigo/{code}"
            print(f"Proxying request to: {target_url}")

            req = urllib.request.Request(target_url)
            
            # Headers to bypass Cloudflare per user suggestion
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0')
            req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
            req.add_header('Accept-Language', 'en-US,en;q=0.5')
            # Add Authorization if necessary
            req.add_header('Authorization', 'Guest')

            with urllib.request.urlopen(req) as response:
                data = response.read()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
                print("Successfully proxied data.")

        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
            self.send_error(e.code, str(e.reason))
        except Exception as e:
            print(f"Proxy Error: {e}")
            self.send_error(500, str(e))

if __name__ == "__main__":
    # Prevent "Address already in use" on restart
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), ProxyHTTPRequestHandler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        print("API Proxy active at /api/proxy?code=832670")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.server_close()
