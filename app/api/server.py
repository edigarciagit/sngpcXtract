import http.server
import socketserver
import urllib.parse
import json
import threading
import glob
import os
import math
from app.services.orchestrator import ExtractionOrchestrator
from app.core.database import Database

PORT = 8000

class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print(f"GET Request: {self.path}", flush=True)
        if self.path == "/" or self.path == "/index.html":
            self.path = "/frontend/index.html"
            super().do_GET()
        elif self.path.startswith("/frontend/"):
            super().do_GET()
        
        # API Endpoints
        elif self.path == '/api/progress':
            self.handle_progress()
        elif self.path.startswith('/api/results'):
            self.handle_results()
        else:
            # Fallback
            if not self.path.startswith("/frontend/") and not self.path.startswith("/api/"):
                self.path = "/frontend" + self.path
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/extract':
            self.handle_extract()
        else:
            self.send_error(404, "Not Found")

    def handle_extract(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        try:
            params = json.loads(post_body.decode('utf-8'))
            reuse_bulk = params.get('reuse', False)
        except:
            reuse_bulk = False

        orchestrator = ExtractionOrchestrator()
        success, msg = orchestrator.start(reuse_bulk=reuse_bulk)
        
        self.send_response(200 if success else 400)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": success, "message": msg}).encode('utf-8'))

    def handle_progress(self):
        orchestrator = ExtractionOrchestrator()
        status = orchestrator.get_status()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(status).encode('utf-8'))

    def handle_results(self):
        try:
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            page = int(params.get('page', [1])[0])
            size = int(params.get('size', [10])[0])
            
            search_query = params.get('search', [None])[0] or params.get('q', [None])[0]
            
            # Retrieve from DB
            total_items = Database.get_total_count(search_query)
            total_pages = math.ceil(total_items / size) if size > 0 else 1
            
            paged_items = Database.get_presentations(page, size, search_query)
            
            response = {
                "content": paged_items,
                "totalPages": total_pages,
                "totalElements": total_items,
                "page": page,
                "size": size
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            print(f"Results Error: {e}")
            self.send_error(500, str(e))

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    # Initialize DB on startup
    Database.init_db()
    with socketserver.TCPServer(("", PORT), ProxyHTTPRequestHandler) as httpd:
        print(f"Server running at http://localhost:{PORT}", flush=True)
        httpd.serve_forever()
