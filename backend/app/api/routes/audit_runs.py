from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import audit_run_repository, get_current_user
from app.aws.auth_service import AuthenticatedUser
from app.aws.s3_service import s3_service

router = APIRouter(prefix="/audit-runs", tags=["audit-runs"])


@router.get("")
async def list_audit_runs(
    limit: int = 50,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve recent audit investigations for the current authenticated user."""
    runs = audit_run_repository.list_user_audit_runs(user.user_id, limit=limit)
    return {"audit_runs": runs, "count": len(runs)}


@router.get("/{run_id}")
async def get_audit_run(
    run_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Reopen a specific audit run from persistent DynamoDB & S3 storage."""
    run = audit_run_repository.get_audit_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Audit run not found.")

    if run.get("user_id") != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have access to this audit run.",
        )

    return run


@router.get("/{run_id}/evidence")
async def get_audit_run_evidence(
    run_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Fetch supporting evidence records associated with an audit run."""
    run = audit_run_repository.get_audit_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Audit run not found.")

    if run.get("user_id") != user.user_id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    details = run.get("details", {})
    result = details.get("result", {})
    return {
        "run_id": run_id,
        "evidence_records": result.get("evidence_sample", []),
        "total_evidence_rows": run.get("evidence_count", 0),
        "columns": result.get("columns", []),
    }


@router.get("/{run_id}/report")
async def get_audit_run_report(
    run_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve secure S3 presigned URL for an audit run report."""
    run = audit_run_repository.get_audit_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Audit run not found.")

    report_key = run.get("report_s3_key")
    if not report_key:
        dataset_id = run.get("dataset_id", "default")
        report_key = f"audit-data/datasets/{user.user_id}/{dataset_id}/reports/{run_id}.pdf"

    presigned_url = s3_service.generate_presigned_url(report_key, expires_in=3600)
    return {
        "run_id": run_id,
        "report_s3_key": report_key,
        "download_url": presigned_url,
    }
