# Database Models and Carbon Logic (MODEL.md)

Here is a quick look at how the database is set up and why we designed it this way.

---

## 1. The Database Schema (Django Models)

We are using 5 simple Django models to handle everything. We chose SQLite because it runs locally instantly without needing any separate database server, which is perfect for this prototype.

* **Organization**: Handles the multi-tenancy. Every tenant has their own name and ID.
* **UserProfile**: Links a standard Django User to an Organization. This ensures users can only see their own organization's carbon data.
* **IngestionJob**: Keeps track of file uploads (SAP, Utility, or Travel). It logs if a job succeeded or failed, and records any error messages.
* **RawRecord**: Stores the exact, unedited JSON payload of the raw data we parsed. **We never edit or delete this file**—it serves as our unalterable source of truth for audits.
* **NormalizedRecord**: The calculated analytics record. It links back to the original `RawRecord`, maps the activity to Scope 1/2/3, normalizes the quantities, and stores the final calculated CO2e in kilograms.
* **AuditTrail**: A simple ledger that logs who made edits, when they did it, and what changed (storing the exact old vs. new values as a JSON delta).

---

## 2. Multi-Tenancy (How we isolate data)
We went with **Shared Schema Multi-Tenancy** using an `Organization` ForeignKey on all main models:
* *Why?* It is fast, simple, and works perfectly on SQLite.
* Every query is filtered by the logged-in user's organization (e.g., `NormalizedRecord.objects.filter(organization=org)`).
* In a production setup, we would layer this with PostgreSQL Row Level Security (RLS) to prevent any database leakage between clients.

---

## 3. Separation of Raw vs. Normalized Data
To ensure audit integrity, we split data into two layers:
1. **The Raw Layer (`RawRecord`)**: The exact file row uploaded. Immutable. No edits allowed.
2. **The Analytical Layer (`NormalizedRecord`)**: The parsed numbers used for metrics. If an analyst corrects a mistake, we update this row, but it always maintains its link to the original `RawRecord` so auditors can compare them.

---

## 4. Carbon Math and Scope Mapping

We map each source to standard carbon scopes during the ingestion step:

* **Scope 1 (Direct Fuels from SAP)**:
  * *Diesel / Heating Oil (Liters)*: $Quantity \times 2.68$ kg CO2e/L
  * *Natural Gas (M3)*: $Quantity \times 2.02$ kg CO2e/M3
  * *LPG (Tonnes)*: $Quantity \times 2,939.00$ kg CO2e/T
* **Scope 2 (Indirect Electricity from Utility Bills)**:
  * Mapped based on the plant's `Meter ID` prefix:
    * Germany (`M-98`): $0.38$ kg CO2e/kWh
    * United States (`M-44`): $0.37$ kg CO2e/kWh
    * India (`M-11`): $0.72$ kg CO2e/kWh
* **Scope 3 (Travel logs from corporate systems)**:
  * *Flights*: Calculates distances using departure/arrival airport coordinate fallbacks (Haversine formula). Applies booking class multipliers:
    * Economy Class: $0.15$ kg CO2e/mile
    * Business Class: $0.43$ kg CO2e/mile
    * First Class: $0.60$ kg CO2e/mile
  * *Hotels*: Stays are multiplied by local overnight factors (e.g., US is $18.5$ kg/night, Germany is $12.2$ kg/night).
  * *Car Rentals*: Miles driven are multiplied by engine factors (e.g., Electric is $0.08$ kg/mile, Gas Compact is $0.22$ kg/mile, SUV is $0.35$ kg/mile).

---

## 5. Audit Trails and Compliance
* Every single manual adjustment, bulk approval, or compliance lock logs an entry in the `AuditTrail`.
* It records the operator, timestamp, and a JSON block showing the exact change (e.g., `{"normalized_quantity": {"old": 500, "new": 600}}`).
* Once an analyst clicks **Lock for Audit**, the record is marked `is_locked = True`. This blocks any further edits or deletions, fulfilling standard compliance requirements.
