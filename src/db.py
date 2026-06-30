import os
import json
from datetime import datetime
import threading

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports.json")
db_lock = threading.Lock()

def _init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump([], f)

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
        import uuid
        report["id"] = str(uuid.uuid4())
    if "timestamp" not in report:
        report["timestamp"] = datetime.now().isoformat()
    if "status" not in report:
        report["status"] = "Pending"
    if "action_taken" not in report:
        report["action_taken"] = "None"
    reports.append(report)
    save_reports(reports)
    return report

def update_report(report_id, update_dict):
    reports = get_reports()
    updated = False
    for r in reports:
        if r.get("id") == report_id:
            r.update(update_dict)
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
    return {
        "total": total,
        "verified": verified,
        "duplicates": duplicates,
        "critical": critical,
        "active_calls": active_calls
    }

def clear_db():
    """Wipes all reports from the database (admin reset)."""
    with db_lock:
        try:
            with open(DB_FILE, "w") as f:
                json.dump([], f)
            return True
        except Exception as e:
            print(f"Error clearing DB: {e}")
            return False
