import sqlite3
import json
import re
from datetime import datetime
from app.core.logger import get_logger

logger = get_logger("database")

DB_NAME = "sngpc.db"

def get_control_list(principio_ativo, classes_str, nome_comercial):
    # Normalize inputs
    pa = (principio_ativo or "").upper()
    cls = (classes_str or "").upper()
    nome = (nome_comercial or "").upper()
    
    def match_substance(substances_list):
        return any(re.search(rf"\b{re.escape(s)}\b", pa) for s in substances_list)
    
    # 1. First, check if the commercial name or class contains the list explicitly
    # e.g. "SULFATO DE MORFINA (PORT 344/98 LISTA A1)"
    for s in ["A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C4", "C5"]:
        pattern = rf"\bLISTA\s*[-–—]?\s*{s}\b"
        if re.search(pattern, nome) or re.search(pattern, cls):
            return s

    # 2. Check by active ingredients (principio_ativo)
    # A1 (Entorpecentes)
    a1_substances = ["MORFINA", "METADONA", "FENTANIL", "OXICODONA", "PETIDINA", "REMIFENTANIL", "SUFENTANIL", "TAPENTADOL", "ALFENTANIL", "HIDROMORFONA"]
    if match_substance(a1_substances):
        return "A1"
        
    # A3 (Psicotrópicos estimulantes)
    a3_substances = ["METILFENIDATO", "LISDEXANFETAMINA"]
    if match_substance(a3_substances):
        return "A3"
        
    # B1 (Psicotrópicos)
    b1_substances = ["CLONAZEPAM", "DIAZEPAM", "ALPRAZOLAM", "LORAZEPAM", "MIDAZOLAM", "BROMAZEPAM", "FENOBARBITAL", "CLOBAZAM", "NITRAZEPAM", "FLURAZEPAM", "CLORDIAZEPÓXIDO", "CLORDIAZEPOXIDO", "CLOXAZOLAM", "ESTAZOLAM", "TRIAZOLAM", "OXAZEPAM", "KETAZOLAM"]
    if match_substance(b1_substances):
        return "B1"
        
    # B2 (Anorexígenos)
    b2_substances = ["SIBUTRAMINA", "ANFEPRAMONA", "FEMPROPOREX", "MAZINDOL"]
    if match_substance(b2_substances):
        return "B2"

    # C2 (Retinóides sistêmicos)
    c2_substances = ["ISOTRETINOINA", "ISOTRETINOÍNA", "ACITRETINA"]
    if match_substance(c2_substances):
        return "C2"

    # C3 (Imunossupressores)
    c3_substances = ["TALIDOMIDA", "LENALIDOMIDA", "POMALIDOMIDA"]
    if match_substance(c3_substances):
        return "C3"

    # C4 (Antirretrovirais)
    c4_substances = ["ZIDOVUDINA", "LAMIVUDINA", "TENOFOVIR", "EFAVIRENZ", "NEVIRAPINA", "LOPINAVIR", "RITONAVIR", "ATAZANAVIR", "DARUNAVIR", "RALTEGRAVIR", "DOLUTEGRAVIR", "ABACAVIR", "ETRAVIRINA", "RILPIVIRINA", "EMTRICITABINA", "COBICISTATE", "ELVITEGRAVIR"]
    if match_substance(c4_substances):
        return "C4"

    # C5 (Anabolizantes)
    c5_substances = ["TESTOSTERONA", "ESTANOZOLOL", "NANDROLONA", "OXANDROLONA", "SOMATROPINA", "OXIMETOLONA", "MESTEROLONA"]
    if match_substance(c5_substances):
        return "C5"
        
    # A2 (Entorpecentes de uso permitido)
    if re.search(r"\bTRAMADOL\b", pa):
        if "A2" in nome or "A2" in cls:
            return "A2"
        return "C1"
    if re.search(r"\bCODEINA\b", pa) or re.search(r"\bCODEÍNA\b", pa):
        if "A2" in nome or "A2" in cls:
            return "A2"
        return "C1"

    # C1 (Outras substâncias sujeitas a controle especial)
    c1_substances = [
        "AMITRIPTILINA", "NORTRIPTILINA", "IMIPRAMINA", "CLOMIPRAMINA", "FLUOXETINA", "SERTRALINA", 
        "PAROXETINA", "CITALOPRAM", "ESCITALOPRAM", "FLUVOXAMINA", "VENLAFAXINA", "DESVENLAFAXINA", 
        "DULOXETINA", "BUPROPIONA", "MIRTAZAPINA", "AGOMELATINA", "TRAZODONA", "VORTIOXETINA", "MAPROTILINA",
        "CLORPROMAZINA", "LEVOMEPROMAZINA", "HALOPERIDOL", "RISPERIDONA", "OLANZAPINA", "QUETIAPINA", 
        "ARIPIPRAZOL", "ZIPRASIDONA", "CLOZAPINA", "SULPIRIDA", "PIMOZIDA", "ZUCLOPENTIXOL", "AMISULPRIDA", 
        "CARIPRAZINA", "PALIPERIDONA", "LURASIDONA", "ASENAPINA",
        "CARBAMAZEPINA", "ACIDO VALPROICO", "ÁCIDO VALPRÓICO", "VALPROATO", "DIVALPROATO", "TOPIRAMATO", 
        "GABAPENTINA", "PREGABALINA", "LAMOTRIGINA", "FENITOINA", "FENITOÍNA", "OXCARBAZEPINA", "VIGABATRINA", 
        "PRIMIDONA", "LACOSAMIDA", "LEVETIRACETAM", "BRIVARACETAM",
        "PRAMIPEXOL", "ROPINIROL", "ROTIGOTINA", "SELEGILINA", "RASAGILINA", "BIPERIDENO",
        "ZOLPIDEM", "ZOPICLONA", "ESZOPICLONA", "BUSPIRONA", "LITIO", "LÍTIO", "MEMANTINA", "DONEPEZILA", 
        "RIVASTIGMINA", "GALANTAMINA", "HALOTANO", "ISOFLURANO", "SEVOFLURANO", "PROPOFOL", "CETAMINA"
    ]
    if match_substance(c1_substances):
        return "C1"

    # AB (Antimicrobianos)
    antibiotic_keywords = ["ANTIBIOTICO", "ANTIBACTERIANO", "CEFALOSPORINA", "PENICILINA", "QUINOLONA", "RIFAMPICINA", "RIFAXIMINA", "SULFA", "TUBERCULOSTATICO", "TUBERCULOSE", "MACROLIDEO", "MACROLÍDEO"]
    has_antibiotic_class = False
    if any(kw in cls for kw in antibiotic_keywords):
        has_antibiotic_class = True
        
    antibiotic_pas = [
        "AMOXICILINA", "CEFALEXINA", "AZITROMICINA", "CIPROFLOXACINO", "CLARITROMICINA", 
        "NEOMICINA", "ERITROMICINA", "METRONIDAZOL", "DOXICICLINA", "SULFAMETOXAZOL", 
        "TRIMETOPRIMA", "AMPICILINA", "CEFALOTINA", "CEFTRIAXONA", "CLINDAMICINA", 
        "GENTAMICINA", "LEVOFLOXACINO", "NORFLOXACINO", "OFLOXACINO", "TETRACICLINA", 
        "RIFAMPICINA", "RIFAXIMINA", "LINEZOLIDA", "MEROPENEM", "IMIPENEM", 
        "CILASTATINA", "VANCOMICINA", "TEICOPLANINA", "POLIMIXINA", "COLISTINA", 
        "SULFADIAZINA", "NITROFURANTOINA", "MINOCICLINA", "CLORANFENICOL"
    ]
    has_antibiotic_pa = match_substance(antibiotic_pas)
    
    if has_antibiotic_class or has_antibiotic_pa:
        return "AB"

    return "N/A"

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
        
        # Check if table bulk_products has the retries and data_atualizacao columns (for backward compatibility / migration)
        cursor.execute("PRAGMA table_info(bulk_products)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'retries' not in columns:
            logger.info("Migrating database bulk_products table: adding 'retries' column...")
            cursor.execute("ALTER TABLE bulk_products ADD COLUMN retries INTEGER DEFAULT 0")
        if 'data_atualizacao' not in columns:
            logger.info("Migrating database bulk_products table: adding 'data_atualizacao' column...")
            cursor.execute("ALTER TABLE bulk_products ADD COLUMN data_atualizacao TEXT")

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bulk_status ON bulk_products (status)')

        # Optimization: High-performance indices for search fields
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_codigo_produto ON presentations (codigo_produto)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nome_lookup ON presentations (nome_comercial)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ativo_lookup ON presentations (principio_ativo)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_registro_lookup ON presentations (numero_registro)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fabricante_lookup ON presentations (fabricante)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ativa ON presentations (ativa)')
        
        # Create table dcb_lookup if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dcb_lookup (
                codigo_dcb TEXT PRIMARY KEY,
                substancia TEXT NOT NULL,
                substancia_normalizada TEXT,
                cas TEXT,
                classificacao TEXT,
                status TEXT DEFAULT 'ATIVO'
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dcb_substancia ON dcb_lookup (substancia_normalizada)')
        
        # Register SQLite UDF function to use the same Python classification rules in SQL
        conn.create_function("get_control_list", 3, get_control_list)
        
        # Migration: Update all existing presentations to align with the ANVISA control list rules
        logger.info("Running migration to update existing presentations to align with ANVISA control lists (A1-C5, AB)...")
        cursor.execute('''
            UPDATE presentations 
            SET lista_controle = get_control_list(principio_ativo, classes_terapeuticas, nome_comercial)
            WHERE lista_controle != get_control_list(principio_ativo, classes_terapeuticas, nome_comercial)
        ''')
        updated_rows = cursor.rowcount
        if updated_rows > 0:
            logger.info(f"Migration: Updated {updated_rows} presentations to their correct ANVISA control lists.")
        
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
        """
        Saves and synchronizes bulk codes to SQLite bulk_products queue table.
        If a code is new, it is inserted as PENDING.
        If it exists but its data_atualizacao from ANVISA has changed, its status is set to PENDING (with retries=0).
        Otherwise, it is kept as is (no change/ignored).
        """
        if not codes:
            return
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            new_count = 0
            modified_count = 0
            
            for item in codes:
                if isinstance(item, dict):
                    code = item.get("codigoProduto")
                    date = item.get("dataAtualizacao")
                else:
                    code = item
                    date = None
                    
                if not code:
                    continue
                
                # Check if item exists in local queue
                cursor.execute("SELECT status, data_atualizacao FROM bulk_products WHERE codigo_produto = ?", (code,))
                row = cursor.fetchone()
                
                if not row:
                    # New product: Insert as PENDING
                    cursor.execute('''
                        INSERT INTO bulk_products (codigo_produto, status, retries, data_atualizacao)
                        VALUES (?, 'PENDING', 0, ?)
                    ''', (code, date))
                    new_count += 1
                else:
                    status, db_date = row
                    # Modified product: if date differs, reset to PENDING and 0 retries
                    if date and db_date != date:
                        cursor.execute('''
                            UPDATE bulk_products
                            SET status = 'PENDING',
                                retries = 0,
                                data_atualizacao = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE codigo_produto = ?
                        ''', (date, code))
                        modified_count += 1
                        
            conn.commit()
            if new_count > 0 or modified_count > 0:
                logger.info(f"Sync Queue Complete: {new_count} new, {modified_count} modified products added/reset to PENDING.")
        except Exception as e:
            logger.error(f"Error synchronizing bulk codes: {e}")
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
                reg_9 = str(numero_registro)[:9] if numero_registro else "N/A"
                lista = get_control_list(principio_ativo, "", nome_comercial)
                rows.append((
                    codigo_produto, nome_comercial, reg_9, "N/A", "N/A", "N/A", "N/A", principio_ativo, "", fabricante, lista, True,
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
                    
                    lista = get_control_list(principio_ativo, classes_str, nome_comercial)


                    
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
                    
                    reg_9 = str(numero_registro)[:9] if numero_registro else (apt.get("registro")[:9] if apt.get("registro") else "N/A")
                    rows.append((
                        codigo_produto, nome_comercial, reg_9, apresentacao, embalagem, validade, tarja, principio_ativo, classes_str, fabricante, lista, ativa,
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
                    err_msg = str(result.get("error") or "").lower()
                    is_rate_limit = "429" in err_msg or "403" in err_msg or "too many requests" in err_msg
                    
                    if is_rate_limit:
                        # For rate limits, keep as PENDING without consuming retries budget
                        cursor.execute('''
                            UPDATE bulk_products
                            SET status = 'PENDING',
                                updated_at = CURRENT_TIMESTAMP
                            WHERE codigo_produto = ?
                        ''', (code,))
                    else:
                        # Increment retries and mark as FAILED if limit reached (5 attempts)
                        cursor.execute('''
                            UPDATE bulk_products
                            SET retries = retries + 1,
                                status = CASE WHEN retries + 1 >= 5 THEN 'FAILED' ELSE 'PENDING' END,
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
    def get_presentations(page=1, size=10, search_query=None, list_filter=None):
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        offset = (page - 1) * size
        where_clauses = []
        params = []
        
        if search_query:
            where_clauses.append("""(
                nome_comercial LIKE ? 
                OR principio_ativo LIKE ? 
                OR numero_registro LIKE ?
                OR registro LIKE ?
                OR classes_terapeuticas LIKE ?
                OR tarja LIKE ?
            )""")
            search_param = f"%{search_query}%"
            params.extend([search_param] * 6)
            
        if list_filter:
            where_clauses.append("lista_controle = ?")
            params.append(list_filter)
            
        where_clause = ""
        if where_clauses:
            where_clause = "WHERE " + " AND ".join(where_clauses)
            
        params.extend([size, offset])
        
        cursor.execute(f'''
            SELECT 
                numero_registro,
                nome_comercial,
                principio_ativo,
                fabricante,
                MAX(ativa) as ativa,
                COUNT(*) as qtd_apresentacoes,
                MAX(updated_at) as updated_at
            FROM presentations 
            {where_clause}
            GROUP BY numero_registro
            ORDER BY updated_at DESC, numero_registro DESC
            LIMIT ? OFFSET ?
        ''', params)
        
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result

    @staticmethod
    def get_total_count(search_query=None, list_filter=None):
        conn = Database._get_connection()
        cursor = conn.cursor()
        
        where_clauses = []
        params = []
        
        if search_query:
            where_clauses.append("""(
                nome_comercial LIKE ? 
                OR principio_ativo LIKE ? 
                OR numero_registro LIKE ?
                OR registro LIKE ?
                OR classes_terapeuticas LIKE ?
                OR tarja LIKE ?
            )""")
            search_param = f"%{search_query}%"
            params.extend([search_param] * 6)
            
        if list_filter:
            where_clauses.append("lista_controle = ?")
            params.append(list_filter)
            
        where_clause = ""
        if where_clauses:
            where_clause = "WHERE " + " AND ".join(where_clauses)
            
        cursor.execute(f'''
            SELECT COUNT(DISTINCT numero_registro) FROM presentations 
            {where_clause}
        ''', params)
        
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

    @staticmethod
    def get_presentations_by_ms(ms_code):
        """Retrieves presentations matching either the 9-digit or 13-digit MS registration code"""
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Clean MS code to keep only digits
        ms_clean = "".join(filter(str.isdigit, str(ms_code)))
        
        cursor.execute('''
            SELECT * FROM presentations 
            WHERE numero_registro = ? OR registro = ?
            ORDER BY id ASC
        ''', (ms_clean, ms_clean))
        
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result

    @staticmethod
    def import_dcb_records(records):
        """
        Inserts or replaces DCB records in dcb_lookup table.
        records: list of tuples (codigo_dcb, substancia, substancia_normalizada, cas, classificacao, status)
        """
        if not records:
            return
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany('''
                INSERT OR REPLACE INTO dcb_lookup (
                    codigo_dcb, substancia, substancia_normalizada, cas, classificacao, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', records)
            conn.commit()
            logger.info(f"Imported {len(records)} DCB records into SQLite.")
        except Exception as e:
            logger.error(f"Error importing DCB records: {e}")
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def get_dcb_by_normalized_name(normalized_name):
        """Finds DCB record matching the normalized name"""
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM dcb_lookup 
            WHERE substancia_normalizada = ?
        ''', (normalized_name,))
        row = cursor.fetchone()
        result = dict(row) if row else None
        conn.close()
        return result

    @staticmethod
    def get_dcb_by_cas(cas_number):
        """Finds DCB record matching the CAS number"""
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM dcb_lookup 
            WHERE cas = ?
        ''', (cas_number,))
        row = cursor.fetchone()
        result = dict(row) if row else None
        conn.close()
        return result

    @staticmethod
    def search_dcb_by_pattern(pattern):
        """Performs a LIKE search on normalized name"""
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM dcb_lookup 
            WHERE substancia_normalizada LIKE ?
        ''', (pattern,))
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result

    @staticmethod
    def get_sync_presentations(page=1, size=100):
        """Retrieves paginated raw presentations for external synchronization"""
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        offset = (page - 1) * size
        cursor.execute('''
            SELECT 
                registro, 
                nome_comercial, 
                principio_ativo, 
                lista_controle, 
                cnpj_empresa, 
                codigo_produto, 
                fabricante, 
                unidade_medida_medicamento, 
                ativa 
            FROM presentations 
            ORDER BY id ASC 
            LIMIT ? OFFSET ?
        ''', (size, offset))
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result

    @staticmethod
    def get_sync_presentations_count():
        """Returns the total number of presentations rows for sync calculations"""
        conn = Database._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM presentations')
        count = cursor.fetchone()[0]
        conn.close()
        return count


