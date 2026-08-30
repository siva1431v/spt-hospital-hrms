# SPT Hospital HRMS — LOP Field Reaching Payroll Record

## 1. Root Cause & Resolution

The background server process (`uvicorn`) was originally launched without `--reload` hours earlier, serving an outdated in-memory bytecode cache to browser requests. The uvicorn daemon has been restarted with `--reload` at `0.0.0.0:8000`.

The payroll calculation and API endpoint `GET /api/v1/payroll/periods/{id}/records` now actively return all 5 required fields:
- `qualifying_late_days`
- `lop_days`
- `lop_deduction`
- `security_fund_deduction`
- `total_deductions`

---

## 2. Raw JSON from Live Server (`GET /api/v1/payroll/periods/1/records`)

Here is the raw JSON returned directly from `http://127.0.0.1:8000/api/v1/payroll/periods/1/records`:

```json
{
  "id": 1,
  "payroll_period_id": 1,
  "employee_id": 13,
  "employee_code": "SPT203",
  "biometric_code": "203",
  "employee_name": "Jagathish",
  "department": "NURSING",
  "basic_salary": 25000.0,
  "gross_salary": 10483.87,
  "present_days": 13.0,
  "absent_days": 18.0,
  "half_days": 0.0,
  "leave_days": 0.0,
  "paid_leave_days": 0.0,
  "off_duty_days": 0.0,
  "qualifying_late_days": 4,
  "loss_of_pay_days": 1.0,
  "lop_days": 1.0,
  "payable_days": 13.0,
  "salary_part": 10483.87,
  "collection": 0.0,
  "lifetime_collection": 0.0,
  "lop_deduction": 806.45,
  "security_fund_deduction": 500.0,
  "total_deductions": 1306.45,
  "deductions": 1306.45,
  "total_salary": 9177.42,
  "net_salary": 9177.42,
  "is_manual_override": false,
  "status": "DRAFT"
}
```

---

## 3. Verified Metrics on Live Server (August 2026)

- **Total Active Records**: 66
- **Records with `lop_days > 0`**: **30**
- **Records with `net_salary < salary_part`**: **63** (30 with LOP + 33 with Savings Fund)
- **Total LOP Days**: 78.0 days

### Six Spot Checks Asserted on Live Server:

| Employee Code & Name | Base Salary | LOP Days | LOP Deduction | Fund Ded | Total Ded | Salary Part | Net Salary |
|---|---|---|---|---|---|---|---|
| **SPT1 (Bio 1) DR Manoj** | ₹25,000 | **5.0 d** | **₹4,032.26** | ₹500.00 | ₹4,532.26 | ₹18,548.39 | **₹14,016.13** |
| **SPT62 (Bio 62) Selladurai** | ₹25,000 | **5.0 d** | **₹4,032.26** | ₹500.00 | ₹4,532.26 | ₹18,548.39 | **₹14,016.13** |
| **SPT6 (Bio 6) Senthil Murugan** | ₹20,000 | **6.0 d** | **₹3,870.97** | ₹500.00 | ₹4,370.97 | ₹14,838.71 | **₹10,467.74** |
| **SPT46 (Bio 46) Sarala** | ₹13,000 | **7.0 d** | **₹2,935.48** | ₹500.00 | ₹3,435.48 | ₹10,064.52 | **₹6,629.04** |
| **SPT15 (Bio 15) Syed Sajith** | ₹13,000 | **7.0 d** | **₹2,935.48** | ₹500.00 | ₹3,435.48 | ₹9,225.81 | **₹5,790.33** |
| **SPT56 (Bio 56) Gnanasundari** | ₹9,500 | **7.0 d** | **₹2,145.16** | ₹500.00 | ₹2,645.16 | ₹7,048.39 | **₹4,403.23** |
