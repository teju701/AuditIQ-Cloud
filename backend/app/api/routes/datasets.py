from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import dataset_store, get_current_user
from app.aws.auth_service import AuthenticatedUser

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
async def list_datasets(user: AuthenticatedUser = Depends(get_current_user)):
    """List all persistent datasets uploaded by the current user."""
    datasets = dataset_store.list_user_datasets(user.user_id)
    return {"datasets": datasets, "count": len(datasets)}


@router.get("/{dataset_id}")
async def get_dataset_details(
    dataset_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve metadata, column profile, and anomalies for a persistent dataset."""
    session = dataset_store.get_dataset(dataset_id)
    if not session:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    if session.user_id and session.user_id != user.user_id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    return {
        "dataset_id": session.dataset_id,
        "user_id": session.user_id,
        "file_name": session.file_name,
        "dataset_hash": session.dataset_hash,
        "rows": len(session.dataframe),
        "columns": list(session.dataframe.columns),
        "created_at": session.created_at,
        "s3_raw_key": session.s3_raw_key,
        "s3_normalized_key": session.s3_normalized_key,
        "schema_profile": session.metadata.get("schema_profile", {}),
        "anomalies": session.metadata.get("anomalies", []),
        "preview": session.dataframe.head(5).to_dict("records"),
    }
