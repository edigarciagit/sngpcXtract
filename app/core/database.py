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
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Optimization: High-performance indices for search fields
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_codigo_produto ON presentations (codigo_produto)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nome_lookup ON presentations (nome_comercial)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ativo_lookup ON presentations (principio_ativo)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_registro_lookup ON presentations (numero_registro)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fabricante_lookup ON presentations (fabricante)')
        
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

            if not apresentacoes:
                rows.append((codigo_produto, nome_comercial, numero_registro, "N/A", "N/A", "N/A", "N/A", principio_ativo, "", fabricante, "N/A"))
            else:
                for apt in apresentacoes:
                    if not apt: continue
                    apresentacao = apt.get("descricao") or apt.get("nome") or apt.get("apresentacao")
                    embalagem_primaria = apt.get("embalagemPrimaria") or {}
                    embalagem = embalagem_primaria.get("descricao")
                    validade = apt.get("validade")
                    tarja = apt.get("tarja")
                    
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
                    
                    rows.append((codigo_produto, nome_comercial, apt.get("registro"), apresentacao, embalagem, validade, tarja, principio_ativo, classes_str, fabricante, lista))
        return rows

    @staticmethod
    def save_product(code, data):
        """Saves a single product's data."""
        Database.save_products_batch([(code, data)])

    @staticmethod
    def save_products_batch(product_list):
        """
        Saves multiple products in a single transaction.
        product_list: list of (code, data) tuples
        """
        if not product_list:
            return

        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            for code, data in product_list:
                if not data: continue
                # Delete existing to avoid dups
                cursor.execute('DELETE FROM presentations WHERE codigo_produto = ?', (code,))
                
                rows = Database._parse_product_data(code, data)
                if rows:
                    cursor.executemany('''
                        INSERT INTO presentations (
                            codigo_produto, nome_comercial, numero_registro, 
                            apresentacao, embalagem, validade,
                            tarja, principio_ativo, classes_terapeuticas,
                            fabricante, lista_controle
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', rows)
            
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
