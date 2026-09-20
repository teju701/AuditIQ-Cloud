from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.api.dependencies import audit_run_repository, dataset_store, get_current_user, run_query_with_cache
from app.aws.auth_service import AuthenticatedUser
from app.aws.s3_service import s3_service
from app.services.report_service import export_finding_pdf
from app.services.reproducibility_service import build_reproducibility_manifest
from app.services.trust_service import compute_trust_score

router = APIRouter(tags=["export"])


@router.post("/export-pdf")
async def export_pdf(
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
):
    dataset_id = str(body.get("dataset_id", "")).strip()
    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required. Upload a dataset first.")

    session = dataset_store.get_dataset(dataset_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Dataset session not found. Please upload again.")

    user_query = str(body.get("query", "")).strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    run_id = str(body.get("run_id") or f"run_{uuid4().hex[:12]}").strip()

    result, cache_meta = run_query_with_cache(session.dataset_hash, user_query, session.dataframe)
    trust = compute_trust_score(result)

    manifest, replay_id = build_reproducibility_manifest(
        dataset_id=session.dataset_id,
        dataset_hash=session.dataset_hash,
        user_query=user_query,
        plan_payload=result.get("pandas_code"),
        execution_mode=result.get("execution_mode", "failed"),
        row_count=result.get("row_count", 0),
    )

    pdf_bytes = export_finding_pdf(
        query=user_query,
        narrative=result["narrative"],
        logic=result.get("logic_explanation", ""),
        trust=trust,
        df_result=result.get("result_df"),
        replay_id=replay_id,
        reproducibility=manifest,
        provenance=result.get("provenance"),
        narrative_grounding=result.get("narrative_grounding"),
        consensus=result.get("consensus"),
    )

    # Persist report to Amazon S3
    s3_report_key = s3_service.save_pdf_report(user.user_id, session.dataset_id, run_id, pdf_bytes)
    audit_run_repository.attach_report_key(run_id, s3_report_key)
    download_url = s3_service.generate_presigned_url(s3_report_key)

    # Return binary response with custom S3 headers for complete client flexibility
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=AuditIQ_{run_id}.pdf",
            "X-Replay-Id": replay_id,
            "X-Run-Id": run_id,
            "X-S3-Key": s3_report_key,
            "X-Download-Url": download_url,
            "X-Cache-Hit": str(bool(cache_meta.get("hit", False))).lower(),
        },
    )


@router.get("/export-pdf/download")
async def download_pdf_local(key: str = Query(...)):
    """Local development fallback endpoint for downloading reports stored in local S3."""
    clean_key = key.replace("/", "\\")
    local_path = Path(__file__).resolve().parents[4] / ".s3_local" / clean_key
    if local_path.exists():
        return FileResponse(
            path=str(local_path),
            media_type="application/pdf",
            filename=local_path.name,
        )
    raise HTTPException(status_code=404, detail="File not found in storage.")
