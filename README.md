# ConstructDesk ERP

A modular Flask + Jinja construction and real estate ERP focused on inventory, customer bookings, receipts, dues, and reports.

## Stack

- Flask
- Jinja templates
- Bootstrap 5
- Vanilla JavaScript
- MongoDB
- ReportLab PDF exports

## Setup

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
$env:MONGO_URI="mongodb://localhost:27017"
$env:MONGO_DB_NAME="construction_erp"
python app.py
```

Open `http://127.0.0.1:5000`.

## Modules

- Dashboard
- Masters
- Inventory
- Customers
- Receipts
- Finance

MongoDB collections used: `companies`, `users`, `audit_logs`, `company_details`, `cost_sheet_templates`, `projects`, `towers`, `flats`, `customers`, `bookings`, `receipts`.
