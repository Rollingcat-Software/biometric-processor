"""Embedding export/import API routes."""

from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
import json

from app.core.container import get_export_embeddings_use_case, get_import_embeddings_use_case
from app.api.middleware.jwt_auth import require_auth, AuthContext

router = APIRouter(
    prefix="/embeddings",
    tags=["Embeddings"],
)


@router.get(
    "/export",
    summary="Export embeddings",
    description=(
        "Exports all face embeddings for a tenant to JSON format. "
        "Useful for backup or migration."
    ),
)
async def export_embeddings(
    auth: AuthContext = Depends(require_auth),
    tenant_id: str = Query(default="default", description="Tenant identifier"),
    format: Literal["json"] = Query(default="json", description="Export format"),
    include_metadata: bool = Query(
        default=True, description="Include user metadata in export"
    ),
) -> JSONResponse:
    """Export embeddings to JSON.

    Args:
        tenant_id: Tenant to export
        format: Export format (json)
        include_metadata: Whether to include metadata

    Returns:
        JSON export data
    """
    # Get use case from container
    use_case = get_export_embeddings_use_case()

    # Execute export
    result = await use_case.execute(
        tenant_id=tenant_id,
        include_metadata=include_metadata,
    )

    return JSONResponse(content=result)


@router.post(
    "/import",
    summary="Import embeddings",
    description=(
        "Imports face embeddings from JSON format. "
        "Supports merge, replace, and skip_existing modes."
    ),
)
async def import_embeddings(
    auth: AuthContext = Depends(require_auth),
    file: UploadFile = File(..., description="JSON export file"),
    mode: Literal["merge", "replace", "skip_existing"] = Form(
        default="merge",
        description="Import mode: merge (update existing), replace (clear first), skip_existing",
    ),
    tenant_id: str = Form(default="default", description="Target tenant"),
) -> Dict[str, Any]:
    """Import embeddings from JSON.

    Args:
        file: JSON export file
        mode: Import mode
        tenant_id: Target tenant

    Returns:
        Import result with statistics
    """
    # Read and parse file
    content = await file.read()
    import_data = json.loads(content.decode("utf-8"))

    # Get use case from container
    use_case = get_import_embeddings_use_case()

    # Execute import
    result = await use_case.execute(
        import_data=import_data,
        mode=mode,
        tenant_id=tenant_id,
    )

    return result
