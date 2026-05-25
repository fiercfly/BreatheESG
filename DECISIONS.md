# Decisions, Assumptions and Edge Cases (DECISIONS.md)

This file covers the main assumptions we made, edge cases we resolved during ingestion, and questions we would ask the Product Manager (PM) if we were working on this live.

---

## 1. How we handled data edge cases

### SAP ERP (Scope 1)
* **German Formatting Quirks**: Standard exports from SAP ALV grids often use semicolons (`;`) instead of commas as column delimiters. They also use commas for decimals (like `1500,50` instead of `1500.50`). Our normalizer detects the delimiter automatically and replaces the decimal commas so Python can convert the strings to decimals.
* **German Headers**: We mapped the standard German columns (`BUKRS` for Company, `WERKS` for Plant, `BUDAT` for Date, `MENGE` for Qty, `MEINS` for Unit, `SGTXT` for Description) to standard English database fields.
* **Cryptic Units**: We mapped typical SAP unit codes (`L` for Liters, `GAL` for Gallons, `M3` for cubic meters, `T` for Tonnes) to standard units automatically.

### Utility Data (Scope 2)
* **Billing cycle durations**: Utility bills aren't neat. The normalizer checks if a bill covers less than 15 days or more than 45 days. If it does, we automatically flag the record as `suspicious_flag = True` because it usually means there is a duplicate upload or a billing glitch.
* **Calendar alignment**: Billing cycles rarely align with calendar months (e.g., April 12 to May 11). The system stores the raw dates exactly, but filters and displays them under the start month in dashboard charts to keep the time-series clean.

### Corporate Travel (Scope 3)
* **Missing Mileage**: Flight data in Concur often has empty mileage columns and only provides airport codes (like `SFO`, `JFK`). We built a custom **Haversine formula calculator** that maps standard airport codes to coordinates and calculates the distance on the fly.
* **Cruise ranges**: Flights under 500 miles have different emission intensities than long-haul flights. The normalizer applies short-haul vs. long-haul thresholds automatically, scaling the emissions based on cabin class (Economy, Business, First).

---

## 2. Z-Score Outlier Detection
We added a statistical sanity check on the backend to flag data entry typos or meter spikes:
* The system computes the mean and standard deviation of carbon emissions (`co2e_kg`) for each category.
* If a newly ingested record has a Z-score greater than **1.5**, we flag it as `suspicious_flag = True` with a clear message (e.g., "Statistical Outlier: CO2e is 2.4 std devs away from the mean"). This highlights anomalies instantly in the UI.

---

## 3. Top 3 Questions for the PM

1. **How should we split utility bills that cross reporting boundaries?**
   * *The Problem:* A bill running from Dec 15 to Jan 14 covers two different years.
   * *Our suggestion:* We should divide the bill's emissions by day (e.g., 17 days in Dec, 14 days in Jan) and book the prorated amounts to their respective calendar months.
2. **What is our registry source of truth for Meter IDs and Plant mapping?**
   * *The Problem:* Currently, we hardcode meter prefixes to local grid mixes (e.g., `M-98` $\rightarrow$ German grid mix).
   * *Our suggestion:* We need an admin registry page where users can upload or map Plant codes and Meter IDs to specific local grid emission coefficients dynamically.
3. **What is the workflow when an analyst rejects a record?**
   * *The Problem:* Currently, analysts can edit or reject rows.
   * *Our suggestion:* Rejected records should go into a specific quarantine state, and the system should send an email notification back to the local plant's procurement lead to upload a corrected export file.
