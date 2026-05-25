# Researched Data Sources and Realism (SOURCES.md)

Here is a summary of the real-world carbon data sources we researched, how our sample files model these formats, and what would break in a real production deployment.

---

## 1. What real-world formats look like

### SAP ERP Exports (Scope 1 - Direct Fuels)
* **Real-World Reality**: In the real world, procurement teams rarely have direct API connections to SAP. Instead, plants configure a scheduled transaction (like `MB51`) that outputs a flat semicolon-separated file (`.csv`) directly into an SFTP share.
* **German Formatting**: Columns typically use German abbreviations (like `BUKRS` for company code, `WERKS` for plant, `BUDAT` for posting date, `MENGE` for quantity, `MEINS` for base unit, and `SGTXT` for segment text). Numbers use decimal commas (e.g., `1200,50` instead of `1200.50`).
* **Our Sample Data (`sap_export.csv`)**: Models this layout perfectly. It uses German headers, semicolon delimiters, German decimal commas, and standard German fuel descriptions (like "Heizoel" for heating oil and "Notstrom" for emergency generator diesel) which our normalizer translates automatically.

### Utility Portals (Scope 2 - Electricity)
* **Real-World Reality**: Facilities operators typically log into utility dashboards (like PG&E or National Grid) to download a CSV invoice export.
* **Main Challenges**: An invoice has a billing start and end date (e.g., April 12 to May 11) that doesn't align with calendar months. Also, the utility rate tariff maps to specific facility Meter IDs.
* **Our Sample Data (`utility_bills.csv`)**: Contains accounts, Meter IDs, distinct consumption in kWh, and non-calendar billing cycles. The normalizer verifies billing durations and maps facility Meter IDs to regional grid mix intensity coefficients.

### Travel Platforms (Scope 3 - Corporate Travel)
* **Real-World Reality**: Modern travel managers (like Concur or Navan) expose REST APIs that return transaction payloads in JSON.
* **Main Challenges**: Flight transactions frequently omit distance and only specify departure/arrival airport codes. Booking classes (Economy, Business, First) scale emission factors drastically.
* **Our Sample Data (`travel_data.json`)**: Models a parsed API response in JSON format. It includes flights, hotel overnights, and car rental parameters. Some flight records have missing distances, which forces our coordinate-based Haversine calculator to run.

---

## 2. Real-World Production Failure Vectors (What would break?)

If we deployed this prototype live inside a large enterprise client today, several edge cases would threaten to break ingestion:

1. **SAP Header Drift**:
   * *The Failure:* A plant updates its SAP ALV grid template, changing the order of columns or renaming `SGTXT` to `BKTXT`. This breaks our positional mapping.
   * *The Fix:* We should add a simple header-mapping GUI on the admin panel, allowing users to align custom column aliases per plant visually without editing code.
2. **Unmapped Airport Codes**:
   * *The Failure:* An employee books a flight to a new regional airport that doesn't exist in our hardcoded dictionary, crashing the Haversine distance calculator.
   * *The Fix:* Integrate a public geocoding API or a database (like OpenFlights) to fetch coordinates of new airport codes dynamically during parsing.
3. **Overlapping Utility Bills**:
   * *The Failure:* A facilities manager uploads a utility CSV that contains duplicate billing periods or overlapping dates for the same meter, causing us to double-count Scope 2 emissions.
   * *The Fix:* Add a unique database constraint checking: `Meter ID + Billing Start Date + Billing End Date` to reject duplicate billing cycles.
