# AuditIQ to AuditIQ Cloud — Migration Notes

This document chronicles the architectural transformation of **AuditIQ** into **AuditIQ Cloud**, detailing the migrated components, AWS native additions, and the core explainability and deterministic audit mechanisms that were strictly preserved.

---

## 1. Architectural Evolution

| Capability | Prototype Architecture (Before) | AuditIQ Cloud AWS Native Architecture (After) |
| :--- | :--- | :--- |
| **Product Name** | AuditIQ (Local prototype) | **AuditIQ Cloud** |
| **Hosting & Web Client** | Local Vite development server | **AWS Amplify Hosting** (React 19 + Vite) |
| **Identity & Access** | Unauthenticated local sessions | **Amazon Cognito User Pools** (Bearer JWT Auth, RBAC: `AUDITOR` / `ADMIN`, IDOR protection) |
| **Backend Execution** | Local uvicorn process | **AWS App Runner** containerized FastAPI |
| **Dataset Storage** | Ephemeral process in-memory storage (lost on restart) | **Amazon S3** (`audit-data/datasets/{user_id}/{dataset_id}/...`) with local storage fallback |
| **Dataset Metadata** | In-memory dictionary | **Amazon DynamoDB** (`AuditIQDatasets` table) |
| **Audit Run Durability** | Unsaved session responses | **Amazon DynamoDB** (`AuditIQAuditRuns`) & S3 result storage with persistent history |
| **AI Planning / Inference** | Google Gemini (`google-generativeai`) | **Amazon Bedrock** (Claude 3 Haiku / Nova) via **Strands Agents SDK** |
| **Observability** | Standard console stdout | **Amazon CloudWatch** structured request logging with latency and request tracing |
| **API Endpoints** | Hardcoded `http://localhost:8000` | Configurable `VITE_API_BASE_URL` with `/datasets` and `/audit-runs` endpoints |

---

## 2. Intentionally Preserved Core Principles

The fundamental premise of AuditIQ remains inviolate:
> **"AI decides; deterministic tools execute."**

1. **Deterministic Safety Architecture**:
   - Zero arbitrary Python code generation.
   - Zero `exec()` or `eval()` or shell invocation.
   - Every question either executes a locked audit metric or routes through safe allow-listed Pandas tools (`find_duplicate_vendors`, `detect_spending_spike`, etc.).

2. **Full Explainability Suite**:
   - **Trust Score**: Algorithm calculating a 0–100 credibility metric based on execution mode, evidence coverage, grounding verification, and consensus.
   - **Narrative Grounding**: Automated claim verification ensuring that narrative numbers match computed evidence.
   - **Dual-Run Consensus**: Configurable independent second-opinion plan verification comparing plan similarity and evidence overlap.
   - **Provenance Tracking**: Full lineage tracing showing source columns, transformations, and filters.
   - **Reproducibility Manifest**: Deterministic SHA-256 fingerprinting generating unique Replay IDs, Query Hashes, Plan Hashes, and Dataset Hashes.
   - **Authentic Evidence**: All tabular records displayed in the UI come directly from deterministic Pandas calculations over the uploaded dataset.

---

## 3. Preserved Baseline Regression

The 6 original locked audit metrics were tested and verified with identical results against `data/transactions.csv`:
- `duplicate_vendor`: **103 records**
- `round_number_invoice`: **10 records**
- `late_payment`: **7 records**
- `no_purchase_order`: **75 records**
- `high_value_transaction`: **307 records**
- `disputed_invoice`: **107 records**

### Newly Added Deterministic Audit Checks:
- `duplicate_invoice`: Identifies repeated invoice numbers billed across transactions.
- `spending_spike`: Statistical outlier detection identifying transactions exceeding 2 standard deviations above mean spend.
- `vendor_concentration`: Flags recurring vendors accounting for over 12% of total cumulative organizational expenditure.
- `split_payment`: Identifies potential invoice splitting structured just below financial policy approval thresholds (e.g. 45k–50k and 90k–100k).
