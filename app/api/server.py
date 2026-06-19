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
import re
from app.services.orchestrator import ExtractionOrchestrator
from app.core.database import Database
from app.core.logger import get_logger

logger = get_logger("api_server")

PORT = 8000

class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        logger.info(f"GET Request: {self.path}")
        if self.path == "/" or self.path == "/index.html":
            self.path = "/frontend/index.html"
            super().do_GET()
        elif self.path == "/api-docs" or self.path == "/api-docs/" or self.path == "/docs" or self.path == "/docs/":
            self.path = "/frontend/swagger.html"
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
        elif self.path.startswith('/api/ms/'):
            self.handle_ms()
        elif self.path.startswith('/api/reports/detail'):
            self.handle_report_detail()
        elif self.path == '/api/reports':
            self.handle_reports_list()
        else:
            # Fallback
            if not self.path.startswith("/frontend/") and not self.path.startswith("/api/"):
                self.path = "/frontend" + self.path
            super().do_GET()

    def do_POST(self):
        logger.info(f"POST Request: {self.path}")
        if self.path == '/api/extract':
            self.handle_extract()
        elif self.path == '/api/confirm':
            self.handle_confirm()
        elif self.path == '/api/stop':
            self.handle_stop()
        elif self.path == '/api/dcb/import':
            self.handle_dcb_import()
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # Redirect standard HTTP server logs to python logger
        logger.info(f"HTTP Server - {self.address_string()} - {format % args}")

    def handle_extract(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        try:
            params = json.loads(post_body.decode('utf-8'))
            reuse_bulk = params.get('reuse', False)
            inactive_only = params.get('inactive_only', False)
        except:
            reuse_bulk = False
            inactive_only = False

        orchestrator = ExtractionOrchestrator()
        success, msg = orchestrator.start(reuse_bulk=reuse_bulk, inactive_only=inactive_only)
        
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
        logger.info(f"Extraction confirmation received: proceed={proceed}. Result: success={success}, msg={msg}")
        
        self.send_response(200 if success else 400)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": success, "message": msg}).encode('utf-8'))

    def handle_stop(self):
        orchestrator = ExtractionOrchestrator()
        orchestrator.stop()
        logger.info("Extraction stop signal processed.")
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "message": "Stop signal sent."}).encode('utf-8'))

    def handle_dcb_import(self):
        from app.services.dcb_service import DCBService
        logger.info("DCB manual import triggered via POST /api/dcb/import")
        success, msg = DCBService.import_from_xlsx()
        logger.info(f"DCB manual import finished. Result: success={success}, msg={msg}")
        
        self.send_response(200 if success else 500)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
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
            list_filter = params.get('list', [None])[0]
            logger.info(f"Fetching presentations results: page={page}, size={size}, query='{search_query}', list_filter='{list_filter}'")
            
            # Retrieve from DB
            total_items = Database.get_total_count(search_query, list_filter)
            total_pages = math.ceil(total_items / size) if size > 0 else 1
            
            paged_items = Database.get_presentations(page, size, search_query, list_filter)
            
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

    def handle_ms(self):
        try:
            parts = self.path.split('/')
            if len(parts) >= 4 and parts[3]:
                ms_code = parts[3]
                if '?' in ms_code:
                    ms_code = ms_code.split('?')[0]
                
                logger.info(f"Querying product details for MS code: {ms_code}")
                presentations = Database.get_presentations_by_ms(ms_code)
                
                # Enrich with DCB details
                from app.services.dcb_service import DCBService
                for p in presentations:
                    p["dcb_list"] = DCBService.get_dcb_details_for_product(p.get("principio_ativo"))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(presentations).encode('utf-8'))
            else:
                self.send_error(400, "Bad Request: Missing MS registration code in path.")
        except Exception as e:
            logger.error(f"Error handling MS query API: {e}")
            self.send_error(500, str(e))

    def handle_export(self):
        try:
            logger.info("Exporting all presentations to CSV file.")
            # Retrieve all data
            data = Database.get_all_presentations_raw()
            
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            
            # Headers
            headers = [
                "ID", "MS (9 dígitos)", "MS Registro (13 dígitos)", "SKU (Código)", "Medicamento", 
                "DCB (Princípio Ativo)", "Apresentação", "Fabricante", "CNPJ Fabricante", 
                "Autorização Empresa", "Lista Controle", "Embalagem", "Validade", "Tarja", "Ativo", 
                "Unidade Medida SNGPC", "Categoria Regulatória", "Existe Bula", "Bula Paciente", 
                "Bula Profissional", "Data Registro Produto", "Data Vencimento Registro Produto", 
                "Medicamento Referência", "Apresentação Fracionada", "Formas Farmacêuticas", 
                "Vias Administração", "Qtd Unidade Medida", "Conservação", "Destinação", 
                "Restrição Hospitais", "Restrição Prescrição", "Restrição Uso", "Atualizado Em"
            ]
            writer.writerow(headers)
            
            for row in data:
                writer.writerow([
                    row.get("id"),
                    row.get("numero_registro"),
                    row.get("registro"),
                    row.get("codigo_produto"),
                    row.get("nome_comercial"),
                    row.get("principio_ativo"),
                    row.get("apresentacao"),
                    row.get("fabricante"),
                    row.get("cnpj_empresa"),
                    row.get("numero_autorizacao_empresa"),
                    row.get("lista_controle"),
                    row.get("embalagem"),
                    row.get("validade"),
                    row.get("tarja"),
                    "SIM" if row.get("ativa") else "NÃO",
                    row.get("unidade_medida_medicamento"),
                    row.get("categoria_regulatoria"),
                    "SIM" if row.get("existe_bula") else "NÃO",
                    row.get("codigo_bula_paciente"),
                    row.get("codigo_bula_profissional"),
                    row.get("data_produto"),
                    row.get("data_vencimento_registro_produto"),
                    row.get("medicamento_referencia"),
                    row.get("apresentacao_fracionada"),
                    row.get("formas_farmaceuticas"),
                    row.get("vias_administracao"),
                    row.get("qtd_unidade_medida"),
                    row.get("conservacao"),
                    row.get("destinacao"),
                    row.get("restricao_hospitais"),
                    row.get("restricao_prescricao"),
                    row.get("restricao_uso"),
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

    def handle_reports_list(self):
        try:
            reports_dir = "data/reports"
            reports = []
            if os.path.exists(reports_dir):
                for filename in os.listdir(reports_dir):
                    if filename.startswith("sync_") and filename.endswith(".json"):
                        filepath = os.path.join(reports_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                reports.append({
                                    "report_id": data.get("report_id"),
                                    "date": data.get("date"),
                                    "start_time": data.get("start_time"),
                                    "end_time": data.get("end_time"),
                                    "duration": data.get("duration"),
                                    "state": data.get("state"),
                                    "message": data.get("message"),
                                    "total_bulk_codes": data.get("total_bulk_codes"),
                                    "scraped_successfully": data.get("scraped_successfully"),
                                    "scraped_failed": data.get("scraped_failed"),
                                    "new_presentations_count": data.get("new_presentations_count"),
                                    "updated_presentations_count": data.get("updated_presentations_count")
                                })
                        except Exception as file_err:
                            logger.error(f"Error reading report file {filename}: {file_err}")
            
            reports.sort(key=lambda x: x.get("report_id", ""), reverse=True)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(reports).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling reports list API: {e}")
            self.send_error(500, str(e))

    def handle_report_detail(self):
        try:
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            report_id = params.get('id', [None])[0]
            
            if not report_id:
                self.send_error(400, "Bad Request: Missing 'id' parameter.")
                return
                
            if not re.match(r'^sync_\d{8}_\d{6}$', report_id):
                self.send_error(400, "Bad Request: Invalid report ID format.")
                return
                
            reports_dir = "data/reports"
            filepath = os.path.join(reports_dir, f"{report_id}.json")
            
            if not os.path.exists(filepath):
                self.send_error(404, f"Report {report_id} not found.")
                return
                
            with open(filepath, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(report_data).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling report detail API: {e}")
            self.send_error(500, str(e))

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    # Initialize DB on startup
    Database.init_db()
    
    # Auto-import DCB list on startup if empty
    try:
        conn = Database._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dcb_lookup")
        count = cursor.fetchone()[0]
        conn.close()
        if count == 0:
            logger.info("DCB database table is empty. Auto-importing DCB entries...")
            from app.services.dcb_service import DCBService
            DCBService.import_from_xlsx()
    except Exception as e:
        logger.error(f"Error checking/auto-importing DCB on startup: {e}")
        
    # Start the Daily Scheduler
    try:
        from app.services.scheduler import DailyScheduler
        scheduler = DailyScheduler()
        scheduler.start()
    except Exception as e:
        logger.error(f"Failed to start Daily Scheduler: {e}")

    with socketserver.TCPServer(("", PORT), ProxyHTTPRequestHandler) as httpd:
        logger.info(f"API Server started and listening at http://localhost:{PORT}")
        httpd.serve_forever()
