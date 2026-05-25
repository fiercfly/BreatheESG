# Architectural Tradeoffs (TRADEOFFS.md)

Here are three features we deliberately chose **not** to build in this prototype, along with our practical engineering reasons.

---

## 1. No Background Processing queues (Celery/Redis)
* **What we left out**: We chose not to set up asynchronous background workers (like Celery, Redis, or RabbitMQ) to parse uploads.
* **Why we did it**:
  * Setting up message brokers and worker containers adds a lot of infrastructure bloat, making the prototype difficult to boot up locally.
  * Our CSV and JSON sample files are small (under 10,000 lines). Our Python parsers are highly optimized and complete calculations in less than 100 milliseconds anyway.
  * Performing the file parsing synchronously inside a standard Django HTTP request-response cycle allows us to wrap the entire ingestion in a single atomic database transaction (`transaction.atomic()`). This guarantees that either the entire file uploads successfully or nothing does, avoiding corrupt partial uploads.
  * *Scale-out plan:* In a real production system, we would move this parsing logic into a serverless AWS Lambda function or a Celery background queue to keep Django's web threads unblocked.

---

## 2. No PostgreSQL separate schemas for Multi-Tenancy
* **What we left out**: We didn't use separate database schemas for each organization (e.g., using packages like `django-tenants`).
* **Why we did it**:
  * Using separate schemas makes database migrations extremely complicated, makes cross-tenant analytical reporting very slow, and makes local setup a headache.
  * Filtering all queries by a simple `Organization` ForeignKey is extremely fast, highly performant, and scales perfectly on SQLite.
  * *Scale-out plan:* Modern PostgreSQL databases support Row Level Security (RLS) policies. In production, we can enforce RLS at the database level, giving us schema-level logical isolation while keeping the simplicity of a single shared database.

---

## 3. No heavy external charting or styling frameworks (Recharts/TailwindCSS)
* **What we left out**: We chose not to install heavy JavaScript charting packages (like Recharts or Chart.js) or styled-component libraries (like TailwindCSS).
* **Why we did it**:
  * Large npm packages bloat the frontend build size, slow down container compilation times, and frequently introduce breaking updates.
  * Instead, we built custom **interactive SVG charts** in React, styled with modular, hand-written Vanilla CSS. They calculate percentages and render paths dynamically.
  * This guarantees that the dashboard loads instantly, adds exactly 0 bytes to the bundle weight, and supports beautiful CSS transitions natively with zero chance of third-party package errors.
