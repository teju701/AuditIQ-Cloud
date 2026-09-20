from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import dataset_store, get_current_user
from app.aws.auth_service import AuthenticatedUser
from app.services.anomaly_service import detect_anomalies
from app.services.schema_service import map_and_profile_dataframe

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    content = await file.read()
    filename = file.filename or "transactions.csv"

    if filename.endswith(".csv"):
        raw_dataframe = pd.read_csv(io.BytesIO(content))
    elif filename.endswith((".xlsx", ".xls")):
        raw_dataframe = pd.read_excel(io.BytesIO(content))
    else:
        raise HTTPException(status_code=400, detail="Only CSV or Excel files supported.")

    mapping_result = map_and_profile_dataframe(raw_dataframe)
    anomalies = detect_anomalies(mapping_result.dataframe)

    session = dataset_store.add_dataset(
        mapping_result.dataframe,
        metadata={
            "semantic_mapping": mapping_result.semantic_mapping,
            "unmapped_columns": mapping_result.unmapped_columns,
            "missing_core_fields": mapping_result.missing_core_fields,
            "schema_profile": mapping_result.schema_profile,
            "anomalies": anomalies,
            "anomaly_summary": {a.get("type", "unknown"): a.get("count", 0) for a in anomalies},
        },
        user_id=user.user_id,
        file_name=filename,
        raw_content=content,
    )

    return {
        "dataset_id": session.dataset_id,
        "user_id": session.user_id,
        "file_name": session.file_name,
        "dataset_hash": session.dataset_hash,
        "s3_raw_key": session.s3_raw_key,
        "s3_normalized_key": session.s3_normalized_key,
        "rows": len(session.dataframe),
        "columns": list(session.dataframe.columns),
        "semantic_mapping": session.metadata.get("semantic_mapping", {}),
        "unmapped_columns": session.metadata.get("unmapped_columns", []),
        "missing_core_fields": session.metadata.get("missing_core_fields", []),
        "schema_profile": session.metadata.get("schema_profile", {}),
        "anomalies": anomalies,
        "preview": session.dataframe.head(5).to_dict("records"),
    }
