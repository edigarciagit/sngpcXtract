import os
import zipfile
import re
import unicodedata
import xml.etree.ElementTree as ET
from app.core.database import Database
from app.core.logger import get_logger

logger = get_logger("dcb_service")

SALT_PREFIXES = [
    "CLORIDRATO DE ", "SULFATO DE ", "ACETATO DE ", "FOSFATO DE ", "FOSFATO DISSODICO DE ",
    "ESTEARATO DE ", "VALERATO DE ", "MALEATO DE ", "MESILATO DE ", "BESILATO DE ",
    "TARTARATO DE ", "BROMIDRATO DE ", "FUMARATO DE ", "PROPIONATO DE ", "BUTILBROMETO DE ",
    "CITRATO DE ", "DIPROPIONATO DE ", "DIACETATO DE ", "CARBONATO DE ", "GLUCONATO DE ",
    "SUCCINATO DE ", "SALICILATO DE ", "VALERATO DE ", "PALMITATO DE ", "PANTOTENATO DE "
]

SALT_SUFFIXES = [
    " SODICO", " CALCICO", " POTASSICO", " DI-HIDRATADO", " SESQUI-HIDRATADO",
    " MONO-HIDRATADO", " HEMI-HIDRATADO", " HIDRATADO", " DISSODICO", " MAGNESIO",
    " MONOHIDRATADO", " DIHIDRATADO", " SESQUIHIDRATADO"
]

CONTROLLED_SUBSTANCES = {
    # Precursors & Psychotropics (Portaria 344)
    "PSEUDOEFEDRINA", "EFEDRINA", "CODEINA", "TRAMADOL", "FENOBARBITAL", "DEXTROPROPOXIFENO",
    "CLONAZEPAM", "DIAZEPAM", "ALPRAZOLAM", "BROMAZEPAM", "LORAZEPAM", "MIDAZOLAM",
    "AMITRIPTILINA", "IMIPRAMINA", "CLOMIPRAMINA", "NORTRIPTILINA", "FLUOXETINA",
    "SERTRALINA", "PAROXETINA", "CITALOPRAM", "ESCITALOPRAM", "VENLAFAXINA", "DULOXETINA",
    "HALOPERIDOL", "CLORPROMAZINA", "LEVOMEPROMAZINA", "RISPERIDONA", "OLANZAPINA",
    "QUETIAPINA", "ARIPIPRAZOL", "ZIPRASIDONA", "SULPIRIDA", "AMISULPRIDA",
    "CARBAMAZEPINA", "OXCARBAZEPINA", "ACIDO VALPROICO", "VALPROATO DE SODIO",
    "DIVALPROATO DE SODIO", "FENITOINA", "GABAPENTINA", "PREGABALINA", "TOPIRAMATO",
    "LAMOTRIGINA", "VIGABATRINA", "LEVETIRACETAM", "CLOBASAM", "ZOLPIDEM", "ZOPICLONA",
    "ESZOPICLONA", "METILFENIDATO", "LISDEXANFETAMINA", "MODAFINILA", "SIBUTRAMINA",
    
    # Antimicrobials (RDC 20/2011)
    "AMOXICILINA", "AMPICILINA", "OXACILINA", "PENICILINA G", "PENICILINA V", "PIPERACILINA",
    "CEFACLOR", "CEFADROXIL", "CEFALEXINA", "CEFALOTINA", "CEFAZOLINA", "CEFEPIMA", 
    "CEFOTAXIMA", "CEFTRIAXONA", "CEFUROXIMA", "AZITROMICINA", "CLARITROMICINA", 
    "ERITROMICINA", "ESPIRAMICINA", "CIPROFLOXACINA", "CIPROFLOXACINO", "LEVOFLOXACINA", 
    "LEVOFLOXACINO", "MOXIFLOXACINO", "NORFLOXACINA", "NORFLOXACINO", "OFLOXACINA", 
    "OFLOXACINO", "AMICACINA", "GENTAMICINA", "NEOMICINA", "ESTREPTOMICINA", 
    "METRONIDAZOL", "DOXICICLINA", "ISONIAZIDA", "LINEZOLIDA", "CLORANFENICOL", 
    "FOSFOMICINA", "NITROFURANTOINA", "SULFAMETOXAZOL", "TRIMETOPRIMA", "RIFAMICINA", 
    "GRAMICIDINA", "BACITRACINA", "POLIMIXINA B", "OXITETRACICLINA", "CLINDAMICINA",
    "ACIDO CLAVULANICO", "CLAVULANATO", "SULBACTAM", "TAZOBACTAM", "TETRACICLINA",
    "CLORTETRACICLINA", "TOBRAMICINA"
}

class DCBService:
    @staticmethod
    def normalize_text(text):
        if not text:
            return ""
        # Clean potential weird replacement character
        text = str(text).replace('\uFFFD', '%')
        nfkd_form = unicodedata.normalize('NFKD', text)
        only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
        # Clean extra spaces and convert to uppercase
        return " ".join(only_ascii.upper().split())

    @staticmethod
    def import_from_xlsx(file_path=r"data/dcb/dcb_list.xlsx"):
        """
        Parses Anvisa's DCB Excel file using pure Python and imports it into SQLite.
        """
        if not os.path.exists(file_path):
            logger.error(f"DCB file not found at {file_path}")
            return False, f"File not found at {file_path}"

        logger.info(f"Parsing DCB file: {file_path}")
        records = []
        try:
            with zipfile.ZipFile(file_path) as z:
                # 1. Parse shared strings to resolve index references
                shared_strings = []
                with z.open('xl/sharedStrings.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    namespace = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
                    for si in root.findall(f'{namespace}si'):
                        t_el = si.find(f'{namespace}t')
                        if t_el is not None:
                            shared_strings.append(t_el.text or "")
                        else:
                            r_texts = [t.text or "" for t in si.findall(f'.//{namespace}t')]
                            shared_strings.append("".join(r_texts))

                # 2. Iterate and parse sheet1.xml row by row
                with z.open('xl/worksheets/sheet1.xml') as f:
                    namespace = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
                    context = ET.iterparse(f, events=('end',))
                    
                    for event, elem in context:
                        if elem.tag == f'{namespace}row':
                            row_idx = elem.get('r')
                            # Skip header rows
                            if row_idx in ('1', '2') or not row_idx:
                                elem.clear()
                                continue
                                
                            row_data = {}
                            for c in elem.findall(f'{namespace}c'):
                                r_attr = c.get('r')
                                t_attr = c.get('t')
                                v = c.find(f'{namespace}v')
                                val = v.text if v is not None else ""
                                
                                if t_attr == 's' and val:
                                    try:
                                        val = shared_strings[int(val)]
                                    except IndexError:
                                        val = ""
                                
                                col_letter = "".join([char for char in r_attr if char.isalpha()])
                                row_data[col_letter] = val
                            
                            # Row columns: A = DCB number, B = Substance name, C = CAS, D = Classification, E = History
                            dcb_num = row_data.get('A', '').strip()
                            substancia = row_data.get('B', '').strip()
                            cas = row_data.get('C', '').strip()
                            classif = row_data.get('D', '').strip()
                            
                            if dcb_num and substancia:
                                # Pad DCB code to 5 digits if it's numeric
                                try:
                                    dcb_code = f"{int(float(dcb_num)):05d}"
                                except ValueError:
                                    dcb_code = dcb_num.zfill(5)
                                    
                                norm_substancia = DCBService.normalize_text(substancia)
                                records.append((
                                    dcb_code,
                                    substancia,
                                    norm_substancia,
                                    cas if cas else None,
                                    classif if classif else 'INF',
                                    'ATIVO'
                                ))
                            elem.clear()
            
            if records:
                Database.import_dcb_records(records)
                logger.info(f"Successfully imported {len(records)} DCB entries.")
                return True, f"Imported {len(records)} DCB entries successfully."
            else:
                return False, "No valid DCB records found in Excel sheet."

        except Exception as e:
            logger.error(f"Failed to parse or import DCB file: {e}")
            return False, str(e)

    @staticmethod
    def split_ingredients(principio_ativo):
        """
        Splits a compound active ingredient string into multiple individual substances.
        Example: "LORATADINA + PSEUDOEFEDRINA" -> ["LORATADINA", "PSEUDOEFEDRINA"]
        """
        if not principio_ativo or principio_ativo == "N/A":
            return []
        norm = DCBService.normalize_text(principio_ativo)
        # Split by: +, /, comma, semicolon, or standalone ' E ' word
        parts = re.split(r'\s*(?:\+|\/|,|;|\s+E\s+)\s*', norm)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def find_dcb_for_substance(substance_name):
        """
        Finds a DCB entry matching a single substance name, with salt and wildcard fallback.
        """
        norm_name = DCBService.normalize_text(substance_name)
        if not norm_name:
            return None

        # 1. Exact match
        match = Database.get_dcb_by_normalized_name(norm_name)
        if match:
            return match

        # 2. Wildcard match (in case there are encoding replacement characters '%')
        if '%' in norm_name:
            matches = Database.search_dcb_by_pattern(norm_name)
            if matches:
                return matches[0]

        # 3. Salt/ester prefix and suffix stripping fallback
        current_name = norm_name
        changed = True
        while changed:
            changed = False
            
            # Strip chemical position prefixes (e.g., "17-", "17,21-", "21-")
            cleaned_name = re.sub(r'^(?:\d+,\d+-|\d+-)\s*', '', current_name)
            if cleaned_name != current_name:
                current_name = cleaned_name
                changed = True
                
            # Strip prefixes
            for pref in SALT_PREFIXES:
                norm_pref = DCBService.normalize_text(pref)
                if current_name.startswith(norm_pref):
                    current_name = current_name[len(norm_pref):].strip()
                    changed = True
                    break
            # Strip suffixes
            for suff in SALT_SUFFIXES:
                norm_suff = DCBService.normalize_text(suff)
                if current_name.endswith(norm_suff):
                    current_name = current_name[:-len(norm_suff)].strip()
                    changed = True
                    break
            
            if changed:
                match = Database.get_dcb_by_normalized_name(current_name)
                if match:
                    return match

        # 4. Containment/LIKE match fallback if length is reasonable
        if len(current_name) > 4:
            matches = Database.search_dcb_by_pattern(f"%{current_name}%")
            if matches:
                # Prefer IFA (active ingredient) or BIO (biological)
                for m in matches:
                    if m.get('classificacao') in ('IFA', 'BIO'):
                        return m
                return matches[0]

        return None

    @staticmethod
    def is_controlled_substance(substance_name):
        """
        Checks if a substance name (after normalization and stripping salts/esters) is controlled.
        """
        norm = DCBService.normalize_text(substance_name)
        if not norm:
            return False
            
        current_name = norm
        changed = True
        while changed:
            changed = False
            # Strip position prefixes
            cleaned_name = re.sub(r'^(?:\d+,\d+-|\d+-)\s*', '', current_name)
            if cleaned_name != current_name:
                current_name = cleaned_name
                changed = True
            # Strip prefixes
            for pref in SALT_PREFIXES:
                norm_pref = DCBService.normalize_text(pref)
                if current_name.startswith(norm_pref):
                    current_name = current_name[len(norm_pref):].strip()
                    changed = True
                    break
            # Strip suffixes
            for suff in SALT_SUFFIXES:
                norm_suff = DCBService.normalize_text(suff)
                if current_name.endswith(norm_suff):
                    current_name = current_name[:-len(norm_suff)].strip()
                    changed = True
                    break
        
        if current_name in CONTROLLED_SUBSTANCES:
            return True
            
        words = current_name.split()
        for w in words:
            if w in CONTROLLED_SUBSTANCES:
                return True
                
        return False

    @staticmethod
    def get_dcb_details_for_product(principio_ativo):
        """
        Enriches a active ingredient with its corresponding DCB codes and details.
        Matches only the controlled substance if the product is a combination with non-controlled active ingredients.
        """
        substances = DCBService.split_ingredients(principio_ativo)
        if len(substances) > 1:
            controlled_subs = [sub for sub in substances if DCBService.is_controlled_substance(sub)]
            if controlled_subs:
                # Filter to display ONLY the controlled substances
                substances = controlled_subs

        results = []
        for sub in substances:
            dcb = DCBService.find_dcb_for_substance(sub)
            if dcb:
                results.append({
                    "ingrediente": sub,
                    "codigo_dcb": dcb["codigo_dcb"],
                    "substancia_oficial": dcb["substancia"],
                    "cas": dcb["cas"],
                    "classificacao": dcb["classificacao"]
                })
            else:
                results.append({
                    "ingrediente": sub,
                    "codigo_dcb": "N/A",
                    "substancia_oficial": sub,
                    "cas": "N/A",
                    "classificacao": "N/A"
                })
        return results
