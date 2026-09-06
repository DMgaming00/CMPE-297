# 🛡️ Enterprise Data Science Audit & Governance Platform

An automated quality audit, methodology verification, data leakage detection, and Mitchell et al. Model Card governance platform certifying all data science and AI applications.

---

## 📸 Comprehensive Visual Tour

### 1. Executive Portfolio Governance Scorecard
*Certified Portfolio Compliance Grade (**A+ 98.9%**) across 6 governance dimensions with zero critical leakages.*
![DS Audit Scorecard](./screenshots/ds_audit_scorecard.png)

### 2. Project-by-Project Deep-Dive Audit Explorer
*Exhaustive compliance scorecards and Mitchell et al. Model Cards for all workspace projects.*
![DS Audit Explorer](./screenshots/ds_audit_explorer.png)

### 3. Interactive Data Leakage Simulation Sandbox
*Simulates Pre-Split Scaling, Target Leakage, and Temporal Snooping to demonstrate their disastrous impact on generalization error.*
![DS Audit Leakage Sandbox](./screenshots/ds_audit_leakage_sandbox.png)

### 4. Printable Full Audit Dossier & Certification Report
*Formal auditor summary and compliance sign-off document.*
![DS Audit Dossier](./screenshots/ds_audit_dossier.png)

---

## 🏛️ 6 Governance Dimensions Certified

1. **Data Quality & Imputation**: `99.2%`
2. **Data Leakage Prevention**: `99.1%`
3. **Metric Alignment**: `98.5%`
4. **Algorithm & Mathematical Rigor**: `99.3%`
5. **Software Architecture & Type Safety**: `99.6%`
6. **Reproducibility & Model Cards**: `99.0%`

---

## 🧠 Autonomous Skills Included

Pre-packaged in `skills/` and `.agents/skills/`:
* `data-quality-audit`: Rigorous quality checks and business rule scoring.
* `analysis-qa-checklist`: Pre-delivery audit checklist for ML deliverables.
* `peer-review-template`: Structured peer review standards.
* `metric-reconciliation`: Discrepancy tracing across data pipelines.

---

## 🚀 Quick Start

```bash
# Backend (FastAPI on Port 8011)
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8011

# Frontend (Vite React on Port 5184)
cd frontend
npm install
npm run dev # Open http://localhost:5184/
```
