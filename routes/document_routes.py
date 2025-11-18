from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal
import os
import time
from pathlib import Path
from middleware.auth_middleware import AuthMiddleware
from services.sandbox_service import SandboxService
from services.audit_service import AuditLogService as AuditService

router = APIRouter()

class DocumentGenerateRequest(BaseModel):
    code: str
    filename: str = "document"
    doc_type: Literal["pdf", "zip"]

@router.post("/documents/generate")
async def generate_document(
    request: DocumentGenerateRequest,
    current_user: dict = Depends(AuthMiddleware.require_auth)
):
    try:
        await AuditService.log_audit(
            user_id=current_user['id'],
            action='document_generate_request',
            resource_type='document',
            details=str({
                'filename': request.filename,
                'doc_type': request.doc_type
            })
        )

        result = await SandboxService.execute_code(
            code=request.code,
            doc_type=request.doc_type,
            filename=request.filename
        )

        if not result['success']:
            await AuditService.log_audit(
                user_id=current_user['id'],
                action='document_generate_failed',
                resource_type='document',
                details=str({'error': result['error']})
            )
            raise HTTPException(status_code=400, detail=result['error'])

        await AuditService.log_audit(
            user_id=current_user['id'],
            action='document_generated',
            resource_type='document',
            details=str({
                'filename': result['filename'],
                'size': result['size'],
                'doc_type': request.doc_type,
                'storage_url': result.get('storage_url', 'local')
            })
        )

        return {
            'success': True,
            'download_url': result['download_url'],
            'filename': result['filename'],
            'size': result['size'],
            'storage_url': result.get('storage_url')
        }

    except HTTPException:
        raise
    except Exception as e:
        await AuditService.log_audit(
            user_id=current_user['id'],
            action='document_generate_error',
            resource_type='document',
            details=str({'error': str(e)})
        )
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.delete("/documents/cleanup")
async def cleanup_old_files(current_user: dict = Depends(AuthMiddleware.require_auth)):
    try:
        generated_dir = Path("generated_files")
        if not generated_dir.exists():
            return {'success': True, 'deleted_count': 0}

        current_time = time.time()
        one_hour = 3600
        deleted_count = 0

        for file_path in generated_dir.iterdir():
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > one_hour:
                    file_path.unlink()
                    deleted_count += 1

        await AuditService.log_audit(
            user_id=current_user['id'],
            action='documents_cleanup',
            resource_type='document',
            details=str({'deleted_count': deleted_count})
        )

        return {
            'success': True,
            'deleted_count': deleted_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en limpieza: {str(e)}")