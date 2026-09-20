import pandas as pd
import numpy as np
from scipy import stats


def _has_columns(df: pd.DataFrame, cols: list[str]) -> bool:
    return all(col in df.columns for col in cols)


def _to_bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)

    lowered = series.astype(str).str.strip().str.lower()
    mapped = lowered.map({"true": True, "1": True, "yes": True, "y": True, "false": False, "0": False, "no": False, "n": False})
    if mapped.notna().any():
        return mapped.fillna(False).astype(bool)

    return series.fillna(False).astype(bool)


def detect_anomalies(df: pd.DataFrame) -> list:
    anomalies = []

    # 1. Duplicate GSTIN with different vendor names
    if _has_columns(df, ["gstin", "vendor_name"]):
        gstin_groups = df.groupby("gstin")["vendor_name"].nunique()
        dup_gstins = gstin_groups[gstin_groups > 1].index.tolist()
        if dup_gstins:
            dup_vendors = df[df["gstin"].isin(dup_gstins)][["vendor_name", "gstin"]].drop_duplicates()
            anomalies.append({
                "type": "Duplicate GSTIN",
                "severity": "high",
                "count": len(dup_gstins),
                "description": f"{len(dup_gstins)} GSTIN(s) are shared by multiple vendor names — possible duplicate or fraudulent vendor registration.",
                "affected": dup_vendors.to_dict("records")
            })

    # 2. Round number invoices
    if "amount" in df.columns:
        amount = pd.to_numeric(df["amount"], errors="coerce")
        round_invoices = df[(amount % 1000 == 0) & amount.notna()]
        if len(round_invoices) > 0:
            anomalies.append({
                "type": "Round Number Invoices",
                "severity": "medium",
                "count": len(round_invoices),
                "description": f"{len(round_invoices)} invoices have amounts exactly divisible by ₹1,000 — a common indicator of fabricated or estimated billing.",
                "affected": []
            })

    # 3. Late payments
    if _has_columns(df, ["payment_date", "due_date"]):
        df_copy = df.copy()
        df_copy["payment_date"] = pd.to_datetime(df_copy["payment_date"], errors="coerce")
        df_copy["due_date"] = pd.to_datetime(df_copy["due_date"], errors="coerce")
        df_copy = df_copy[df_copy["payment_date"].notna() & df_copy["due_date"].notna()].copy()
        df_copy["days_late"] = (df_copy["payment_date"] - df_copy["due_date"]).dt.days
        late = df_copy[df_copy["days_late"] > 30]
        if len(late) > 0:
            anomalies.append({
                "type": "Late Payments",
                "severity": "medium",
                "count": len(late),
                "description": f"{len(late)} payments were made more than 30 days past due date. Max delay: {int(late['days_late'].max())} days.",
                "affected": []
            })

    # 4. High-value transactions with no PO
    if _has_columns(df, ["amount", "has_purchase_order"]):
        amount = pd.to_numeric(df["amount"], errors="coerce")
        has_po = _to_bool_series(df["has_purchase_order"])
        no_po_high = df[(amount > 10000) & (~has_po)]
        if len(no_po_high) > 0:
            total_exposure = pd.to_numeric(no_po_high["amount"], errors="coerce").sum()
            anomalies.append({
                "type": "No Purchase Order",
                "severity": "high",
                "count": len(no_po_high),
                "description": f"{len(no_po_high)} transactions above ₹10,000 have no associated purchase order. Total exposure: ₹{total_exposure:,.2f}",
                "affected": []
            })

    # 5. Statistical outliers in amount (Z-score > 3)
    if "amount" in df.columns:
        amount = pd.to_numeric(df["amount"], errors="coerce")
        valid_amount = amount.dropna()
        if len(valid_amount) >= 3 and valid_amount.std(ddof=0) > 0:
            z_scores = np.abs(stats.zscore(valid_amount))
            outlier_index = valid_amount.index[z_scores > 3]
            outliers = df.loc[outlier_index]
            if len(outliers) > 0:
                anomalies.append({
                    "type": "Statistical Outliers",
                    "severity": "low",
                    "count": len(outliers),
                    "description": f"{len(outliers)} transaction amounts are statistical outliers (Z-score > 3) compared to the overall distribution.",
                    "affected": []
                })

    return anomalies