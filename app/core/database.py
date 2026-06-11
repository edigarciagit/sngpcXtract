import sqlite3
import json
from datetime import datetime
from app.core.logger import get_logger

logger = get_logger("database")

DB_NAME = "sngpc.db"

class Database:
    @staticmethod
    def _get_connection():
        # Optimization: increased timeout for concurrent access and WAL mode support
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        return conn

    @staticmethod
    def init_db():
        logger.info(f"Initializing database: {DB_NAME}")
        conn = Database._get_connection()
        cursor = conn.cursor()
        
        # Optimization: Enable WAL (Write-Ahead Logging) mode
        # This allows concurrent reads and writes without blocking
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=-10000') # 10MB cache
        cursor.execute('PRAGMA temp_store=MEMORY')
        
        # Check if table presentations exists and has the new column
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='presentations'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(presentations)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'unidade_medida_medicamento' not in columns:
                logger.info("New schema detected. Dropping old presentations table...")
                cursor.execute("DROP TABLE presentations")
        
        # Create table if not exists with optimized types
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presentations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_produto INTEGER,
                nome_comercial TEXT,
                numero_registro TEXT,
                apresentacao TEXT,
                embalagem TEXT,
                validade TEXT,
                tarja TEXT,
                principio_ativo TEXT,
                classes_terapeuticas TEXT,
                fabricante TEXT,
                lista_controle TEXT,
                ativa BOOLEAN,
                unidade_medida_medicamento INTEGER,
                categoria_regulatoria TEXT,
                existe_bula BOOLEAN,
                codigo_bula_paciente TEXT,
                codigo_bula_profissional TEXT,
                data_produto TEXT,
                data_vencimento_registro_produto TEXT,
                medicamento_referencia TEXT,
                cnpj_empresa TEXT,
                numero_autorizacao_empresa TEXT,
                registro TEXT,
                apresentacao_fracionada TEXT,
                formas_farmaceuticas TEXT,
                vias_administracao TEXT,
                qtd_unidade_medida TEXT,
                conservacao TEXT,
                destinacao TEXT,
                restricao_hospitais TEXT,
                restricao_prescricao TEXT,
                restricao_uso TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create queue table for bulk products if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bulk_products (
                codigo_produto INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'PENDING',
                retries INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if table bulk_products has the retries column (for backward compatibility / migration)
        cursor.execute("PRAGMA table_info(bulk_products)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'retries' not in columns:
            logger.info("Migrating database bulk_products table: adding 'retries' column...")
            cursor.execute("ALTER TABLE bulk_products ADD COLUMN retries INTEGER DEFAULT 0")

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bulk_status ON bulk_products (status)')

        # Optimization: High-performance indices for search fields
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_codigo_produto ON presentations (codigo_produto)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nome_lookup ON presentations (nome_comercial)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ativo_lookup ON presentations (principio_ativo)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_registro_lookup ON presentations (numero_registro)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fabricante_lookup ON presentations (fabricante)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ativa ON presentations (ativa)')
        
        conn.commit()
        conn.close()

    @staticmethod
    def clear_data():
        """Deletes all data from the presentations table"""
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM presentations')
            conn.commit()
            logger.info("Database cleared.")
        except Exception as e:
            logger.error(f"Error clearing database: {e}")
        finally:
            conn.close()

    @staticmethod
    def clear_bulk_codes():
        """Deletes all bulk codes from the queue table"""
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM bulk_products')
            conn.commit()
            logger.info("Bulk products queue cleared.")
        except Exception as e:
            logger.error(f"Error clearing bulk queue: {e}")
        finally:
            conn.close()

    @staticmethod
    def save_bulk_codes(codes):
        """Saves bulk codes directly to SQLite bulk_products queue table"""
        if not codes:
            return
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            rows = []
            for item in codes:
                if isinstance(item, dict):
                    c = item.get("codigoProduto")
                else:
                    c = item
                if c:
                    rows.append((c, 'PENDING'))
            cursor.executemany('''
                INSERT OR IGNORE INTO bulk_products (codigo_produto, status)
                VALUES (?, ?)
            ''', rows)
            conn.commit()
            logger.info(f"Saved {len(rows)} bulk codes to SQLite bulk_products queue.")
        except Exception as e:
            logger.error(f"Error saving bulk codes: {e}")
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def get_bulk_codes(status=None):
        """Reads bulk codes from SQLite queue table"""
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            if status:
                cursor.execute('SELECT codigo_produto FROM bulk_products WHERE status = ?', (status,))
            else:
                cursor.execute('SELECT codigo_produto FROM bulk_products')
            rows = cursor.fetchall()
            return [{"codigoProduto": row[0]} for row in rows]
        except Exception as e:
            logger.error(f"Error reading bulk codes from SQLite: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def update_bulk_code_status(code, status):
        """Updates the queue status of a specific code"""
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE bulk_products 
                SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE codigo_produto = ?
            ''', (status, code))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating bulk code status: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_unidade_medida_medicamento(apresentacao, formas_farmaceuticas_list, embalagem):
        """Calculates the SNGPC unit code: 1 = Caixa, 2 = Frasco"""
        apresentacao_upper = (apresentacao or "").upper()
        embalagem_upper = (embalagem or "").upper()
        formas_upper = [f.upper() for f in (formas_farmaceuticas_list or [])]
        
        frasco_keywords = [
            "FRASCO", "FR ", "FRASCO-AMPOLA", "AMPOLA", "AMP ", "FLACONETE", "BISNAGA", 
            "SERINGA", "GOTAS", "XAROPE", "SOLUÇÃO", "SUSPENSÃO", "SOL ", "SUSP ", "XPE ", "SOL ORAL"
        ]
        
        for kw in frasco_keywords:
            if kw in apresentacao_upper or kw in embalagem_upper:
                return 2
            for f in formas_upper:
                if kw in f:
                    return 2
        return 1

    @staticmethod
    def _parse_product_data(code, data):
        """Helper to extract rows from product JSON."""
        rows = []
        if not data: return rows

        # Handle list or dict root
        if isinstance(data, list):
            root_objs = data
        else:
            content = data.get("content", []) if "content" in data else [data]
            root_objs = content

        for root in root_objs:
            if not root: continue

            prod_data = root.get("produto") or {}
            codigo_produto = prod_data.get("codigo") or root.get("codigoProduto") or code
            nome_comercial = prod_data.get("nome") or root.get("nomeComercial")
            numero_registro = prod_data.get("numeroRegistro") or root.get("numeroRegistro")
            
            apresentacoes = root.get("apresentacoes", [])
            empresa_obj = root.get("empresa") or (root.get("produto") or {}).get("empresa") or {}
            fabricante = empresa_obj.get("razaoSocial") or empresa_obj.get("nomeFantasia") or "N/A"
            principio_ativo = root.get("principioAtivo") or (root.get("produto") or {}).get("principioAtivo") or "N/A"

            # Root fields
            categoria_regulatoria = root.get("categoriaRegulatoria")
            existe_bula = root.get("existeBula")
            codigo_bula_paciente = root.get("codigoBulaPaciente")
            codigo_bula_profissional = root.get("codigoBulaProfissional")
            data_produto = root.get("dataProduto")
            data_vencimento_registro_produto = root.get("dataVencimentoRegistro")
            medicamento_referencia = root.get("medicamentoReferencia")
            cnpj_empresa = empresa_obj.get("cnpj")
            numero_autorizacao_empresa = empresa_obj.get("numeroAutorizacao")

            if not apresentacoes:
                rows.append((
                    codigo_produto, nome_comercial, numero_registro, "N/A", "N/A", "N/A", "N/A", principio_ativo, "", fabricante, "N/A", True,
                    1, categoria_regulatoria, existe_bula, codigo_bula_paciente, codigo_bula_profissional, data_produto, data_vencimento_registro_produto, medicamento_referencia,
                    cnpj_empresa, numero_autorizacao_empresa, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"
                ))
            else:
                for apt in apresentacoes:
                    if not apt: continue
                    apresentacao = apt.get("descricao") or apt.get("nome") or apt.get("apresentacao")
                    embalagem_primaria = apt.get("embalagemPrimaria") or {}
                    embalagem = embalagem_primaria.get("descricao")
                    validade = apt.get("validade")
                    tarja = apt.get("tarja")
                    ativa = apt.get("ativa", True)
                    
                    classes = root.get("classesTerapeuticas", [])
                    classes_str = ", ".join(classes) if isinstance(classes, list) else str(classes)
                    
                    lista = "N/A"
                    for c in (classes if isinstance(classes, list) else [str(classes)]):
                        if "portaria 344" in c.lower() or "lista" in c.lower():
                            symbols = ["A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C4", "C5"]
                            for s in symbols:
                                 if s in c:
                                    lista = s
                                    break
                    
                    # Nested presentation lists to strings
                    formas_farmaceuticas_list = apt.get("formasFarmaceuticas", [])
                    formas_farmaceuticas = ", ".join(formas_farmaceuticas_list) if isinstance(formas_farmaceuticas_list, list) else str(formas_farmaceuticas_list)
                    
                    vias_administracao_list = apt.get("viasAdministracao", [])
                    vias_administracao = ", ".join(vias_administracao_list) if isinstance(vias_administracao_list, list) else str(vias_administracao_list)
                    
                    conservacao_list = apt.get("conservacao", [])
                    conservacao = ", ".join(conservacao_list) if isinstance(conservacao_list, list) else str(conservacao_list)
                    
                    destinacao_list = apt.get("destinacao", [])
                    destinacao = ", ".join(destinacao_list) if isinstance(destinacao_list, list) else str(destinacao_list)
                    
                    restricao_prescricao_list = apt.get("restricaoPrescricao", [])
                    restricao_prescricao = ", ".join(restricao_prescricao_list) if isinstance(restricao_prescricao_list, list) else str(restricao_prescricao_list)
                    
                    restricao_uso_list = apt.get("restricaoUso", [])
                    restricao_uso = ", ".join(restricao_uso_list) if isinstance(restricao_uso_list, list) else str(restricao_uso_list)
                    
                    # Unidade Medida calculation
                    unidade_medida_medicamento = Database.get_unidade_medida_medicamento(apresentacao, formas_farmaceuticas_list, embalagem)
                    
                    rows.append((
                        codigo_produto, nome_comercial, apt.get("registro"), apresentacao, embalagem, validade, tarja, principio_ativo, classes_str, fabricante, lista, ativa,
                        unidade_medida_medicamento, categoria_regulatoria, existe_bula, codigo_bula_paciente, codigo_bula_profissional, data_produto, data_vencimento_registro_produto, medicamento_referencia,
                        cnpj_empresa, numero_autorizacao_empresa, apt.get("registro"), apt.get("apresentacaoFracionada"), formas_farmaceuticas, vias_administracao, apt.get("qtdUnidadeMedida"),
                        conservacao, destinacao, apt.get("restricaoHospitais"), restricao_prescricao, restricao_uso
                    ))
        return rows

    @staticmethod
    def save_product(code, data):
        """Saves a single product's data."""
        Database.save_products_batch([(code, data)])

    @staticmethod
    def save_products_batch(batch_data):
        """
        Saves multiple products and updates their queue statuses/retries.
        Supports:
          1. List of (code, data) tuples (compatibility mode)
          2. Dict of {code: {"success": bool, "data": dict/None, "error": str/None}}
        """
        if not batch_data:
            return

        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            # Normalize batch data to a unified format
            if isinstance(batch_data, list):
                batch_results = {}
                for item in batch_data:
                    if isinstance(item, tuple) and len(item) == 2:
                        code, data = item
                        batch_results[code] = {
                            "success": True if data else False,
                            "data": data,
                            "error": None if data else "Scrape returned empty data"
                        }
            else:
                batch_results = batch_data

            for code, result in batch_results.items():
                if result["success"]:
                    data = result["data"]
                    if not data:
                        continue
                    # Delete existing to avoid dups
                    cursor.execute('DELETE FROM presentations WHERE codigo_produto = ?', (code,))
                    
                    rows = Database._parse_product_data(code, data)
                    if rows:
                        cursor.executemany('''
                            INSERT INTO presentations (
                                codigo_produto, nome_comercial, numero_registro, 
                                apresentacao, embalagem, validade,
                                tarja, principio_ativo, classes_terapeuticas,
                                fabricante, lista_controle, ativa,
                                unidade_medida_medicamento, categoria_regulatoria, existe_bula,
                                codigo_bula_paciente, codigo_bula_profissional, data_produto,
                                data_vencimento_registro_produto, medicamento_referencia, cnpj_empresa,
                                numero_autorizacao_empresa, registro, apresentacao_fracionada,
                                formas_farmaceuticas, vias_administracao, qtd_unidade_medida,
                                conservacao, destinacao, restricao_hospitais,
                                restricao_prescricao, restricao_uso
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', rows)
                    
                    # Mark this code as PROCESSED in the queue table
                    cursor.execute('''
                        UPDATE bulk_products 
                        SET status = 'PROCESSED', updated_at = CURRENT_TIMESTAMP 
                        WHERE codigo_produto = ?
                    ''', (code,))
                else:
                    # Increment retries and mark as FAILED if limit reached (3 attempts)
                    cursor.execute('''
                        UPDATE bulk_products
                        SET retries = retries + 1,
                            status = CASE WHEN retries + 1 >= 3 THEN 'FAILED' ELSE 'PENDING' END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE codigo_produto = ?
                    ''', (code,))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Batch DB Error: {e}")
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def get_presentations(page=1, size=10, search_query=None):
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        offset = (page - 1) * size
        where_clause = ""
        params = []
        
        if search_query:
            where_clause = """
                WHERE nome_comercial LIKE ? 
                OR principio_ativo LIKE ? 
                OR numero_registro LIKE ?
                OR classes_terapeuticas LIKE ?
                OR tarja LIKE ?
            """
            search_param = f"%{search_query}%"
            params = [search_param] * 5
            
        params.extend([size, offset])
        
        cursor.execute(f'''
            SELECT * FROM presentations 
            {where_clause}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
        ''', params)
        
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result

    @staticmethod
    def get_total_count(search_query=None):
        conn = Database._get_connection()
        cursor = conn.cursor()
        
        if search_query:
            search_param = f"%{search_query}%"
            cursor.execute('''
                SELECT COUNT(*) FROM presentations 
                WHERE nome_comercial LIKE ? 
                OR principio_ativo LIKE ? 
                OR numero_registro LIKE ?
                OR classes_terapeuticas LIKE ?
                OR tarja LIKE ?
            ''', (search_param, search_param, search_param, search_param, search_param))
        else:
            cursor.execute('SELECT COUNT(*) FROM presentations')
            
        count = cursor.fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def get_all_presentations_raw():
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM presentations ORDER BY codigo_produto')
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result
