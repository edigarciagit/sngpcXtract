import http.server
import socketserver
import urllib.parse
import json
import threading
import glob
import os
import math
import csv
import io
from app.services.orchestrator import ExtractionOrchestrator
from app.core.database import Database
from app.core.logger import get_logger

logger = get_logger("api_server")

PORT = 8000

class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        logger.debug(f"GET Request: {self.path}")
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
        elif self.path == '/api/export':
            self.handle_export()
        elif self.path == '/api/logs':
            self.handle_logs()
        else:
            # Fallback
            if not self.path.startswith("/frontend/") and not self.path.startswith("/api/"):
                self.path = "/frontend" + self.path
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/extract':
            self.handle_extract()
        elif self.path == '/api/confirm':
            self.handle_confirm()
        elif self.path == '/api/stop':
            self.handle_stop()
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
        
        if success:
            logger.info("Extraction process triggered via API.")
        else:
            logger.warning(f"Failed to trigger extraction: {msg}")

    def handle_confirm(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        try:
            params = json.loads(post_body.decode('utf-8'))
            proceed = params.get('proceed', True)
        except:
            proceed = True

        orchestrator = ExtractionOrchestrator()
        success, msg = orchestrator.confirm_extraction(proceed=proceed)
        
        self.send_response(200 if success else 400)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": success, "message": msg}).encode('utf-8'))

    def handle_stop(self):
        orchestrator = ExtractionOrchestrator()
        orchestrator.stop()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "message": "Stop signal sent."}).encode('utf-8'))

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
            logger.error(f"Error handling results API: {e}")
            self.send_error(500, str(e))

    def handle_export(self):
        try:
            # Retrieve all data
            data = Database.get_all_presentations_raw()
            
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            
            # Headers
            headers = ["ID", "MS", "SKU (Código)", "Medicamento", "DCB (Princípio Ativo)", "Apresentação", "Fabricante", "Lista Controle", "Embalagem", "Validade", "Tarja", "Ativo", "Atualizado Em"]
            writer.writerow(headers)
            
            for row in data:
                writer.writerow([
                    row.get("id"),
                    row.get("numero_registro"),
                    row.get("codigo_produto"),
                    row.get("nome_comercial"),
                    row.get("principio_ativo"),
                    row.get("apresentacao"),
                    row.get("fabricante"),
                    row.get("lista_controle"),
                    row.get("embalagem"),
                    row.get("validade"),
                    row.get("tarja"),
                    "SIM" if row.get("ativa") else "NÃO",
                    row.get("updated_at")
                ])
                
            csv_content = output.getvalue()
            # Add BOM for Excel UTF-8 compatibility
            csv_content_bom = '\ufeff' + csv_content
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename=sngpc_data.csv')
            self.end_headers()
            self.wfile.write(csv_content_bom.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error handling export API: {e}")
            self.send_error(500, str(e))

    def handle_logs(self):
        try:
            log_file = "logs/app.log"
            max_lines = 100
            
            if not os.path.exists(log_file):
                lines = []
            else:
                with open(log_file, 'r', encoding='utf-8') as f:
                    # Read all lines and take last N
                    all_lines = f.readlines()
                    lines = all_lines[-max_lines:]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"lines": lines}).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling logs API: {e}")
            self.send_error(500, str(e))

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    # Initialize DB on startup
    Database.init_db()
    with socketserver.TCPServer(("", PORT), ProxyHTTPRequestHandler) as httpd:
        logger.info(f"API Server started and listening at http://localhost:{PORT}")
        httpd.serve_forever()
