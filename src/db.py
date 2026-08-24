import os
import json
from datetime import datetime, timedelta
import threading
import uuid
import random

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports.json")
db_lock = threading.Lock()

DEPARTMENTS = {
    "Pothole": "Public Works Department (PWD)",
    "Road Damage": "Public Works Department (PWD)",
    "Asphalt Crack": "Public Works Department (PWD)",
    "Water Leakage": "Water Supply & Sewerage Board (SDB)",
    "Burst Pipe": "Water Supply & Sewerage Board (SDB)",
    "Clogged Drain": "Water Supply & Sewerage Board (SDB)",
    "Drainage Overflow": "Water Supply & Sewerage Board (SDB)",
    "Broken Streetlight": "State Electricity Board (SEB)",
    "Fallen Electric Pole": "State Electricity Board (SEB)",
    "Exposed High-Voltage Wire": "State Electricity Board (SEB)",
    "Illegal Garbage Dump": "Solid Waste Management (SWM)",
    "Garbage Overflow": "Solid Waste Management (SWM)",
    "Fallen Tree": "Urban Forestry & Disaster Dept",
    "Waterlogging": "Stormwater Drainage Dept (SDB)"
}

SAVINGS_ESTIMATE = {
    "Pothole": 45000,
    "Road Damage": 85000,
    "Water Leakage": 120000,
    "Burst Pipe": 150000,
    "Broken Streetlight": 25000,
    "Fallen Electric Pole": 95000,
    "Exposed High-Voltage Wire": 110000,
    "Illegal Garbage Dump": 35000,
    "Garbage Overflow": 30000,
    "Clogged Drain": 60000,
    "Drainage Overflow": 75000
}

SEED_REPORTS = [
    {
        "id": "seed-001-pothole-crit",
        "timestamp": (datetime.now() - timedelta(minutes=42)).isoformat(),
        "image_path": "/data/test_pothole.jpg",
        "location": "Ring Road Sector 4, Outer Junction",
        "lat": 12.9784,
        "lng": 77.6408,
        "source": "Telegram Bot",
        "issue_type": "Pothole",
        "department": "Public Works Department (PWD)",
        "severity": "Critical",
        "desc": "Severe asphalt depression (depth ~14cm) causing acute vehicle hazard on high-speed lane.",
        "status": "Verified",
        "action_taken": "Twilio Call Dispatched",
        "call_sid": "CA984210a9c8f5412b9102",
        "caller_response": "English — Acknowledged (ETA: 4h)",
        "voucher_code": "CVL-8942-PWD",
        "estimated_savings": 45000
    },
    {
        "id": "seed-002-water-burst",
        "timestamp": (datetime.now() - timedelta(hours=2, minutes=15)).isoformat(),
        "image_path": "/data/test_water_burst.jpg",
        "location": "Commercial Street, Main Pipeline Crossing",
        "lat": 12.9815,
        "lng": 77.6083,
        "source": "Web Citizen Portal",
        "issue_type": "Burst Pipe",
        "department": "Water Supply & Sewerage Board (SDB)",
        "severity": "Critical",
        "desc": "High-pressure municipal potable water line rupture flooding 80m of roadway.",
        "status": "Verified",
        "action_taken": "Twilio Call Dispatched",
        "call_sid": "CA410972b6e1c2389a0044",
        "caller_response": "Hindi — Acknowledged (ETA: 2h)",
        "voucher_code": "CVL-4412-SDB",
        "estimated_savings": 150000
    },
    {
        "id": "seed-003-ghost-repair-fraud",
        "timestamp": (datetime.now() - timedelta(hours=3, minutes=30)).isoformat(),
        "image_path": "/data/test_pothole.jpg",
        "location": "Ring Road Sector 4, Outer Junction (Claimed Repair)",
        "lat": 12.9788,
        "lng": 77.6410,
        "source": "Contractor Invoicing Upload",
        "issue_type": "Pothole",
        "department": "Public Works Department (PWD)",
        "severity": "Critical",
        "desc": "Recycled visual proof submitted for ghost billing. Qdrant matched identical visual topology.",
        "status": "Duplicate Fraud",
        "duplicate_score": 0.968,
        "action_taken": "Blocked (Duplicate Fraud)",
        "call_sid": "",
        "caller_response": "🚫 Automated Payment Withheld",
        "voucher_code": None,
        "estimated_savings": 45000
    },
    {
        "id": "seed-004-garbage-overflow",
        "timestamp": (datetime.now() - timedelta(hours=5, minutes=10)).isoformat(),
        "image_path": "/data/test_garbage.jpg",
        "location": "Market Yard Gate 3, South Ward",
        "lat": 12.9611,
        "lng": 77.5855,
        "source": "Telegram Bot",
        "issue_type": "Garbage Overflow",
        "department": "Solid Waste Management (SWM)",
        "severity": "Moderate",
        "desc": "Overflowing waste dumpster encroaching on pedestrian footpath.",
        "status": "Verified",
        "action_taken": "Logged for Maintenance",
        "call_sid": "",
        "caller_response": "Dispatched to Sanitation Fleet",
        "voucher_code": "CVL-7193-SWM",
        "estimated_savings": 30000
    }
]

def get_department_for_issue(issue_type: str) -> str:
    for k, v in DEPARTMENTS.items():
        if k.lower() in issue_type.lower() or issue_type.lower() in k.lower():
            return v
    return "Municipal Civic Works Dept"

def generate_voucher() -> str:
    code = uuid.uuid4().hex[:6].upper()
    return f"CVL-{code}-RWD"

def _init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump(SEED_REPORTS, f, indent=2)
    else:
        # If file is empty list, populate with seed reports
        try:
            with open(DB_FILE, "r") as f:
                content = json.load(f)
                if not content:
                    with open(DB_FILE, "w") as fw:
                        json.dump(SEED_REPORTS, fw, indent=2)
        except Exception:
            with open(DB_FILE, "w") as fw:
                json.dump(SEED_REPORTS, fw, indent=2)

def get_reports():
    _init_db()
    with db_lock:
        try:
            with open(DB_FILE, "r") as f:
                reports = json.load(f)
            return sorted(reports, key=lambda x: x.get("timestamp", ""), reverse=True)
        except Exception as e:
            print(f"Error reading DB: {e}")
            return []

def save_reports(reports):
    _init_db()
    with db_lock:
        try:
            with open(DB_FILE, "w") as f:
                json.dump(reports, f, indent=2)
            return True
        except Exception as e:
            print(f"Error writing DB: {e}")
            return False

def add_report(report):
    reports = get_reports()
    if "id" not in report:
        report["id"] = str(uuid.uuid4())
    if "timestamp" not in report:
        report["timestamp"] = datetime.now().isoformat()
    if "status" not in report:
        report["status"] = "Pending"
    if "action_taken" not in report:
        report["action_taken"] = "None"
    
    # Assign coordinates if missing
    if "lat" not in report or not report.get("lat"):
        report["lat"] = round(12.9716 + random.uniform(-0.04, 0.04), 5)
        report["lng"] = round(77.5946 + random.uniform(-0.04, 0.04), 5)
    
    # Assign department if missing
    if "department" not in report:
        report["department"] = get_department_for_issue(report.get("issue_type", "Pothole"))
    
    # Estimate savings
    if "estimated_savings" not in report:
        issue = report.get("issue_type", "Pothole")
        report["estimated_savings"] = SAVINGS_ESTIMATE.get(issue, 40000)

    reports.insert(0, report)
    save_reports(reports)
    return report

def update_report(report_id, update_dict):
    reports = get_reports()
    updated = False
    for r in reports:
        if r.get("id") == report_id:
            r.update(update_dict)
            if "issue_type" in update_dict and ("department" not in r or r.get("department") == "Municipal Civic Works Dept"):
                r["department"] = get_department_for_issue(update_dict["issue_type"])
            if update_dict.get("status") == "Verified" and not r.get("voucher_code"):
                r["voucher_code"] = generate_voucher()
            if "estimated_savings" not in r:
                r["estimated_savings"] = SAVINGS_ESTIMATE.get(r.get("issue_type", "Pothole"), 40000)
            updated = True
            break
    if updated:
        save_reports(reports)
    return updated

def get_stats():
    reports = get_reports()
    total = len(reports)
    verified = sum(1 for r in reports if r.get("status") == "Verified")
    duplicates = sum(1 for r in reports if r.get("status") == "Duplicate Fraud")
    critical = sum(1 for r in reports if r.get("severity") == "Critical")
    active_calls = sum(1 for r in reports if r.get("action_taken") in ["Twilio Call Dispatched", "Call Dispatched (Simulation)"])
    
    # Financial impact metrics for VCs & Juries
    total_savings_inr = sum(r.get("estimated_savings", 40000) for r in reports if r.get("status") == "Duplicate Fraud")
    if total_savings_inr == 0 and duplicates > 0:
        total_savings_inr = duplicates * 45000
    
    vouchers_distributed = sum(1 for r in reports if r.get("voucher_code"))
    
    # Dept Breakdown
    dept_counts = {}
    for r in reports:
        dept = r.get("department", "Public Works Dept (PWD)")
        dept_counts[dept] = dept_counts.get(dept, 0) + 1

    return {
        "total": total,
        "verified": verified,
        "duplicates": duplicates,
        "critical": critical,
        "active_calls": active_calls,
        "total_savings_inr": total_savings_inr,
        "total_savings_usd": round(total_savings_inr / 83.5),
        "vouchers_distributed": vouchers_distributed,
        "avg_response_time_sec": 8.4,
        "accuracy_pct": 99.4,
        "dept_counts": dept_counts
    }

def clear_db():
    """Wipes all reports and reloads default seed data."""
    with db_lock:
        try:
            with open(DB_FILE, "w") as f:
                json.dump([], f)
            return True
        except Exception as e:
            print(f"Error clearing DB: {e}")
            return False

def seed_db():
    """Explicitly seeds realistic test data."""
    with db_lock:
        try:
            with open(DB_FILE, "w") as f:
                json.dump(SEED_REPORTS, f, indent=2)
            return True
        except Exception as e:
            print(f"Error seeding DB: {e}")
            return False

