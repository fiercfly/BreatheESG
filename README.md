# Breathe ESG Ingestion and Review Dashboard

An enterprise-grade Django REST Framework + React (Vite) prototype for ingesting, normalizing, and auditing carbon emissions data across Scope 1 (Direct SAP procurement), Scope 2 (Indirect utility bills), and Scope 3 (Indirect Concur corporate travel API logs).

---

## Features Built

1. **SAP ALV ERP Ingestion (Scope 1 - Direct Fuels)**:
   - Dynamic translation of cryptic German ALV column headers (BUKRS, WERKS, BUDAT, MENGE, MEINS, WRBTR, SGTXT).
   - Dynamic numeric parsing (handling German comma decimal separators).
   - Facility lookup based on plant codes.
2. **Electricity Portal Ingestion (Scope 2 - Indirect Energy)**:
   - Billing duration anomaly detection (flags intervals under 15 or over 45 days).
   - Maps meter IDs to specific regional utility grid mix emission coefficients.
3. **Travel API Ingestion (Scope 3 - Corporate Travel)**:
   - Automatic Great-Circle Haversine distance calculations using airport coordinate fallbacks for flights with missing mileage.
   - Flight cabin class multipliers and country-specific hotel room-night coefficients.
4. **Anomalous Outlier Flags**:
   - Integrates a backend Z-Score statistical analysis engine.
   - Automatically flags data rows exceeding 1.5 standard deviations from their category average as suspicious.
5. **Ledger-Style Compliance Audit Trail**:
   - Every single manual adjustment, bulk approval, or auditor locking operation logs a detailed delta change dictionary and locks rows against further editing.
6. **Premium Clean React UI**:
   - Styled from scratch in pure Vanilla CSS with dark/light themes.
   - Built custom interactive responsive SVG charts (emissions timeline, carbon scope donut distributions).
   - Side-by-side expandable row review panel showing the Verbatim Raw JSON (unalterable source of truth) side-by-side with transparent carbon formulas.

---

## Technical Architecture & Docs

Please refer to the following root-level deliverables for in-depth documentation:
- MODEL.md: Relational Database Models & normalization equations.
- DECISIONS.md: Handled data complexity, edge cases, and PM alignments.
- TRADEOFFS.md: Deliberate architectural exclusions and justifications.
- SOURCES.md: Industry research details, sample data mapping, and failure vectors.

---

## Quickstart Guide (Local Setup)

Ensure you have Python 3.11+ and Node.js 20+ installed.

### 1. Run Backend Server (Django REST)
Open a terminal in the root directory:
```powershell
# Navigate to backend
cd backend

# Execute dev server
python manage.py runserver
```
The backend API will boot up on http://127.0.0.1:8000/.

### 2. Run Frontend Server (React + Vite)
Open a new terminal in the root directory:
```powershell
# Navigate to frontend
cd frontend

# Execute dev server
npm run dev
```
The React dashboard will boot up on http://localhost:5173/. Open it in your browser!

### 3. Ingesting Real-World Sample Data
Click on Dashboard and navigate to the Data Ingest Center to upload the fabricated realistic files in the sample_data/ directory:
- sap_export.csv (Select SAP CSV)
- utility_bills.csv (Select Utility CSV)
- travel_data.json (Select Travel JSON)
