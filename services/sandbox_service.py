import subprocess
import tempfile
import os
import re
import asyncio
from pathlib import Path
from typing import Dict, Any
import logging
from services.supabase_service import get_supabase_service

logger = logging.getLogger(__name__)

class SandboxService:
    TIMEOUT = 15
    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_CODE_LENGTH = 50000
    MAX_MEMORY_MB = 256
    MAX_CPU_TIME = 10

    ALLOWED_IMPORTS = {
        'reportlab', 'reportlab.lib', 'reportlab.lib.pagesizes', 
        'reportlab.platypus', 'reportlab.lib.colors', 'reportlab.pdfgen',
        'reportlab.pdfgen.canvas', 'reportlab.lib.styles', 'reportlab.lib.enums',
        'reportlab.platypus.tables', 'reportlab.platypus.paragraph',
        'reportlab.graphics', 'reportlab.graphics.shapes', 'reportlab.lib.units',
        'zipfile', 'io', 'BytesIO', 'datetime', 'json', 're', 'math', 'random',
        'A4', 'letter', 'inch', 'canvas', 'SimpleDocTemplate', 'Paragraph',
        'Spacer', 'PageBreak', 'Table', 'TableStyle', 'colors',
        'getSampleStyleSheet', 'lib', 'platypus', 'TA_CENTER', 'TA_LEFT', 
        'TA_RIGHT', 'TA_JUSTIFY', 'enums'
    }

    ALLOWED_FILE_EXTENSIONS = {'.pdf', '.zip'}

    BLACKLIST_PATTERNS = [
        r'\bos\.system\b',
        r'\bos\.popen\b',
        r'\bos\.spawn\b',
        r'\bos\.fork\b',
        r'\bos\.exec\b',
        r'\bos\.kill\b',
        r'\bos\.environ\b',
        r'\bos\.putenv\b',
        r'\bsubprocess\b',
        r'\beval\b',
        r'\bexec\b',
        r'\b__import__\b',
        r'\bcompile\b',
        r'\brmdir\b',
        r'\bunlink\b',
        r'\bshutil\b',
        r'\bsocket\b',
        r'\bftplib\b',
        r'\burllib\b',
        r'\brequests\b',
        r'\bhttpx\b',
        r'\b__file__\b',
        r'\bglobs?\(\)',
        r'\blocals?\(\)',
        r'\bvars\b',
        r'\bdir\s*\(',
        r'\bgetattr\b',
        r'\bsetattr\b',
        r'\bdelattr\b',
        r'\b__dict__\b',
        r'\b__code__\b',
        r'\b__globals__\b',
        r'\bpickle\b',
        r'\bmarshal\b',
        r'\bctypes\b',
        r'\bsys\.path\b',
        r'\bsys\.modules\b',
        r'/etc/',
        r'/proc/',
        r'/sys/',
        r'/dev/',
        r'/root/',
        r'/home/',
        r'\.\./',
        r'\bchmod\b',
        r'\bchown\b',
        # Block PIL/Pillow imports (no image file support)
        r'from\s+PIL\s+import',
        r'import\s+PIL\b',
        r'from\s+Pillow\s+import',
        r'import\s+Pillow\b',
    ]

    @staticmethod
    def validate_code(code: str) -> Dict[str, Any]:
        if not code or not code.strip():
            return {
                'valid': False,
                'error': 'El código no puede estar vacío'
            }

        if len(code) > SandboxService.MAX_CODE_LENGTH:
            return {
                'valid': False,
                'error': f'El código excede el límite de {SandboxService.MAX_CODE_LENGTH} caracteres'
            }

        for pattern in SandboxService.BLACKLIST_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return {
                    'valid': False,
                    'error': f'Código rechazado: contiene operaciones no permitidas (patrón de seguridad detectado)'
                }

        import_pattern = r'(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)'
        imports = re.findall(import_pattern, code)

        for imp in imports:
            base_import = imp.split('.')[0]
            if base_import not in SandboxService.ALLOWED_IMPORTS:
                return {
                    'valid': False,
                    'error': f'Import no permitido: {imp}. Solo se permiten: {", ".join(sorted(SandboxService.ALLOWED_IMPORTS))}'
                }

        return {'valid': True}

    @staticmethod
    async def execute_code(code: str, doc_type: str, filename: str = "document") -> Dict[str, Any]:
        # Validate ONLY the user's code before wrapping it
        validation = SandboxService.validate_code(code)
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['error']
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            script_path = temp_path / "script.py"
            output_ext = '.pdf' if doc_type == 'pdf' else '.zip'
            output_filename = f"{filename}{output_ext}"
            output_path = temp_path / output_filename

            # Prepare restricted builtins that only allow writing to output_file
            # This wrapper code is safe and doesn't need validation
            full_code = f"""
import sys
import builtins
import os
sys.path.insert(0, '{temp_dir}')

output_file = r"{output_path}"
_temp_dir = r"{temp_dir}"

# Override open to only allow writing to output_file or BytesIO
_original_open = builtins.open
def _safe_open(file, mode='r', *args, **kwargs):
    if 'w' in mode or 'a' in mode or '+' in mode:
        # Convertir a ruta absoluta para comparación
        file_str = str(file)
        
        # Permitir BytesIO y StringIO (empiezan con '<')
        if file_str.startswith('<'):
            return _original_open(file, mode, *args, **kwargs)
        
        # Normalizar rutas para comparación
        try:
            file_abs = os.path.abspath(file_str)
            output_abs = os.path.abspath(output_file)
            
            # Permitir si es el archivo de salida o está en el directorio temporal
            if file_abs == output_abs or file_abs.startswith(_temp_dir):
                return _original_open(file, mode, *args, **kwargs)
        except:
            pass
        
        raise PermissionError(f"Writing to files is restricted. Only output_file is allowed.")
    return _original_open(file, mode, *args, **kwargs)

builtins.open = _safe_open

{code}
"""

            script_path.write_text(full_code, encoding='utf-8')

            try:
                process = await asyncio.create_subprocess_exec(
                    'python3', str(script_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(temp_path)
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=SandboxService.TIMEOUT
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.communicate()
                    return {
                        'success': False,
                        'error': f'Timeout: La ejecución excedió {SandboxService.TIMEOUT} segundos'
                    }

                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='replace')
                    stdout_msg = stdout.decode('utf-8', errors='replace') if stdout else ''
                    return {
                        'success': False,
                        'error': f'Error en ejecución: {error_msg}',
                        'stdout': stdout_msg
                    }

                # Buscar archivos PDF o ZIP generados en el directorio temporal
                generated_files = [
                    f for f in temp_path.iterdir() 
                    if f.is_file() and f.suffix.lower() in SandboxService.ALLOWED_FILE_EXTENSIONS and f.name != 'script.py'
                ]
                
                if not generated_files:
                    temp_files = list(temp_path.iterdir())
                    temp_files_str = ', '.join([f.name for f in temp_files])
                    
                    return {
                        'success': False,
                        'error': f'El código no generó ningún archivo PDF/ZIP. Archivos encontrados: [{temp_files_str}]. Asegúrate de guardar el resultado en un archivo .pdf o .zip',
                        'stdout': stdout.decode('utf-8', errors='replace') if stdout else '',
                        'stderr': stderr.decode('utf-8', errors='replace') if stderr else ''
                    }
                
                # Usar el primer archivo generado
                output_path = generated_files[0]

                file_extension = output_path.suffix.lower()
                if file_extension not in SandboxService.ALLOWED_FILE_EXTENSIONS:
                    return {
                        'success': False,
                        'error': f'Tipo de archivo no permitido: {file_extension}. Solo se permiten: {", ".join(SandboxService.ALLOWED_FILE_EXTENSIONS)}'
                    }

                file_size = output_path.stat().st_size
                if file_size == 0:
                    return {
                        'success': False,
                        'error': 'El archivo generado está vacío'
                    }

                if file_size > SandboxService.MAX_FILE_SIZE:
                    return {
                        'success': False,
                        'error': f'Archivo generado excede el límite de {SandboxService.MAX_FILE_SIZE / 1024 / 1024}MB'
                    }

                generated_dir = Path("generated_files")
                generated_dir.mkdir(exist_ok=True)

                final_path = generated_dir / output_filename

                with open(output_path, 'rb') as src, open(final_path, 'wb') as dst:
                    dst.write(src.read())
                
                result = {
                    'success': True,
                    'path': str(final_path),
                    'filename': output_filename,
                    'size': file_size,
                    'stdout': stdout.decode('utf-8', errors='replace') if stdout else '',
                    'download_url': f"/downloads/{output_filename}"  # URL local por defecto
                }

                # Intentar subir a Supabase Storage
                try:
                    supabase = get_supabase_service()
                    if supabase:
                        with open(output_path, 'rb') as f:
                            file_data = f.read()

                        # Generar nombre único con timestamp para evitar conflictos
                        import time
                        timestamp = int(time.time())
                        storage_path = f"documents/{timestamp}_{output_filename}"
                        
                        # Subir a bucket 'generated-files' con metadata
                        upload_result = supabase.storage.from_('generated-files').upload(
                            storage_path,
                            file_data,
                            {
                                'content-type': 'application/pdf' if doc_type == 'pdf' else 'application/zip',
                                'cacheControl': '3600',  # Cache por 1 hora
                                'upsert': 'false'
                            }
                        )

                        # Obtener URL pública
                        public_url = supabase.storage.from_('generated-files').get_public_url(storage_path)
                        # Agregar parámetro download para forzar descarga en lugar de vista previa
                        download_url = f"{public_url}?download={output_filename}"
                        result['storage_url'] = public_url
                        result['storage_path'] = storage_path
                        # Priorizar URL de Supabase Storage con parámetro de descarga
                        result['download_url'] = download_url
                        logger.info(f"✅ File uploaded to Supabase Storage: {download_url}")
                        logger.info(f"📅 File will be auto-deleted after ~1 hour via lifecycle policy")
                except Exception as e:
                    logger.warning(f"⚠️ Could not upload to Supabase Storage: {str(e)}")
                    # No falla si no se puede subir, el archivo local sigue disponible

                return result

            except Exception as e:
                return {
                    'success': False,
                    'error': f'Error inesperado: {str(e)}'
                }