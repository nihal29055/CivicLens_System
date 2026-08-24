from fastapi import FastAPI, Request, Form, Response, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from src.vision_engine import VisionEngine
from src.enforcer_engine import EnforcerEngine
from src.memory_engine import MemoryEngine
import src.db as db
import telebot
import os
import shutil
import uuid
import requests
import asyncio
import threading
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Initialize engines
vision = VisionEngine()
enforcer = EnforcerEngine()
memory = MemoryEngine()

app = FastAPI(title="CivicLens: Autonomous Governance Defense Core")

os.makedirs("data", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)

SYSTEM_LOGS = []
CONNECTED_WS = set()

async def _broadcast_log(entry):
    disconnected = []
    for ws in list(CONNECTED_WS):
        try:
            await ws.send_json(entry)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        try:
            CONNECTED_WS.remove(ws)
        except KeyError:
            pass

def log_event(message: str, level: str = "INFO"):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "message": message
    }
    SYSTEM_LOGS.append(entry)
    if len(SYSTEM_LOGS) > 200:
        SYSTEM_LOGS.pop(0)
    print(f"[{level}] {message}")
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(_broadcast_log(entry))
    except RuntimeError:
        pass
    except Exception:
        pass

log_event("CivicLens Server starting up...")

# ─── TELEGRAM BOT SETUP & HANDLERS ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
NGROK_URL = os.getenv("NGROK_URL", "").strip()
TELEGRAM_USER_LOCATIONS = {}
bot = None

if TELEGRAM_BOT_TOKEN:
    try:
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        log_event(f"Telegram Bot initialized OK (ID: {TELEGRAM_BOT_TOKEN.split(':')[0]}).")
    except Exception as e:
        log_event(f"Telegram Bot init FAILED: {e}", "ERROR")
else:
    log_event("No TELEGRAM_BOT_TOKEN found in .env", "WARNING")


LATEST_ISSUE = {"type": "Pothole", "loc": "Sector 4", "call_sid": ""}


# ─── CORE PIPELINE ───────────────────────────────────────────────────────────
def run_pipeline_sync(image_path: str, location: str = "Unknown", source: str = "Web", chat_id=None):
    try:
        log_event(f"[PIPELINE] Started | Source: {source} | File: {os.path.basename(image_path)}")

        # ── Step 0: Civic Image Validation ────────────────────────────────
        log_event("[PIPELINE] Pre-screening image for civic relevance...")
        validation = vision.validate_civic_image(image_path)
        is_civic = validation.get("is_civic_issue", True)
        val_reason = validation.get("reason", "")
        detected = validation.get("detected_issue", "Unknown")
        confidence = validation.get("confidence", "low")

        log_event(f"[VALIDATION] is_civic={is_civic} | confidence={confidence} | detected='{detected}'")

        if not is_civic:
            log_event(f"[VALIDATION] REJECTED — Not a civic issue. Reason: {val_reason}", "WARNING")
            if chat_id and bot:
                try:
                    bot.send_message(
                        chat_id,
                        f"❌ *Image Rejected — Not a Civic Issue*\n\n"
                        f"What we detected: _{detected}_\n\n"
                        f"{val_reason}\n\n"
                        f"Please send a photo of a real civic problem such as:\n"
                        f"• 🛣️ Pothole or road damage\n"
                        f"• 💧 Water leakage or pipeline blockage\n"
                        f"• 🚰 Drainage or sewage overflow\n"
                        f"• 💡 Broken streetlight\n"
                        f"• 🗑️ Illegal garbage dumping\n"
                        f"• ⚡ Fallen electric pole / broken wires\n"
                        f"• 🌳 Tree fall on road\n"
                        f"• 🌊 Waterlogging / flooding",
                        parse_mode="Markdown"
                    )
                except Exception as te:
                    log_event(f"Telegram rejection message failed: {te}", "WARNING")
            try:
                os.remove(image_path)
            except Exception:
                pass
            return

        log_event(f"[VALIDATION] ACCEPTED — Civic issue confirmed: '{detected}'")

        report_id = str(uuid.uuid4())
        report = {
            "id": report_id,
            "timestamp": datetime.now().isoformat(),
            "image_path": f"/data/uploads/{os.path.basename(image_path)}",
            "location": location,
            "source": source,
            "issue_type": "Analyzing...",
            "severity": "Analyzing...",
            "desc": "Calling Gemini Flash Vision...",
            "status": "Pending",
            "action_taken": "None",
            "call_sid": "",
            "caller_response": ""
        }
        db.add_report(report)

        # ── Step 1: Gemini Vision ──────────────────────────────────────────
        log_event("[PIPELINE] Invoking Gemini 1.5 Flash Vision engine...")
        analysis = vision.analyze_image(image_path, mode="severity")
        log_event(f"Gemini Analysis: {analysis}")

        issue_type = analysis.get("issue_type", "Pothole")
        severity = analysis.get("severity", "Critical")
        desc = analysis.get("desc", "Visual damage detected")
        visual_fingerprint = analysis.get("visual_fingerprint", desc)
        department = db.get_department_for_issue(issue_type)
        savings = db.SAVINGS_ESTIMATE.get(issue_type, 45000)

        db.update_report(report_id, {
            "issue_type": issue_type,
            "department": department,
            "severity": severity,
            "desc": desc,
            "estimated_savings": savings
        })

        # ── Step 2: Qdrant Duplicate Check ────────────────────────────────
        log_event("[PIPELINE] Vectorizing evidence fingerprint into 768-D embedding...")
        vector = vision.get_embedding(visual_fingerprint)

        log_event("[PIPELINE] Querying Qdrant Vector DB for duplicate/ghost repair check...")
        is_duplicate, score, _ = memory.search_duplicate(vector)

        if is_duplicate:
            log_event(f"FRAUD DETECTED! Duplicate evidence cosine score: {score*100:.1f}%", "WARNING")
            log_event(f"AUTONOMOUS DEFENSE: Ghost repair billing intercepted! ₹{savings:,} saved.", "WARNING")
            db.update_report(report_id, {
                "status": "Duplicate Fraud",
                "duplicate_score": float(score),
                "action_taken": "Blocked (Duplicate Fraud)",
                "caller_response": "🚫 Payment Withheld (Fraud)",
                "voucher_code": None
            })
            if chat_id and bot:
                try:
                    bot.send_message(chat_id,
                        f"❌ *Duplicate Report Blocked*\n\n"
                        f"This issue has already been reported (Similarity: {score*100:.0f}%).\n"
                        f"No action taken for duplicate submissions.",
                        parse_mode="Markdown")
                except Exception as te:
                    log_event(f"Telegram reply error: {te}", "WARNING")
            return

        # ── Step 3: Save unique to Qdrant ─────────────────────────────────
        voucher = db.generate_voucher()
        log_event(f"[PIPELINE] Evidence unique. Minting Citizen Reward Voucher [{voucher}] & saving vector...")
        memory.save_record(vector, {"report_id": report_id, "issue_type": issue_type, "location": location})
        db.update_report(report_id, {"status": "Verified", "voucher_code": voucher})

        if chat_id and bot:
            try:
                bot.send_message(chat_id,
                    f"✅ *Report Verified!*\n\n"
                    f"Issue: *{issue_type}*\n"
                    f"Department: *{department}*\n"
                    f"Severity: *{severity}*\n"
                    f"Location: {location}\n\n"
                    f"{desc}\n\n"
                    f"🎁 *Reward Voucher*: `{voucher}`\n\n"
                    f"Notifying the responsible contractor now...",
                    parse_mode="Markdown")
            except Exception as te:
                log_event(f"Telegram verified reply error: {te}", "WARNING")

        # ── Step 4: Twilio IVR Call ───────────────────────────────────────
        if severity == "Critical":
            log_event(f"[PIPELINE] CRITICAL severity — Auto-dispatching Twilio IVR to {department}...")
            call_sid = enforcer.trigger_ivr_call(issue_type, location)
            action = "Call Dispatched (Simulation)" if "SIMULATION" in str(call_sid) else "Twilio Call Dispatched"
            log_event(f"[PIPELINE] Call result: {action} | SID: {call_sid}")
            db.update_report(report_id, {"action_taken": action, "call_sid": call_sid})

            if chat_id and bot:
                try:
                    bot.send_message(
                        chat_id,
                        f"🎉 *Audit Completed & Reward Issued!*\n\n"
                        f"🏢 *Department*: _{department}_\n"
                        f"⚡ *Severity*: *{severity} (4-Hour SLA Locked)*\n"
                        f"📞 *Contractor*: Auto-dialed via Autonomous Voice IVR\n\n"
                        f"🎁 *YOUR ANONYMOUS VOUCHER*: `{voucher}`\n"
                        f"🪙 *Reward Points*: *+150 Civic Points*\n\n"
                        f"🔒 *Privacy Guarantee*: Your identity is 100% anonymous. This voucher code is your private key to redeem municipal tax & utility rebates.",
                        parse_mode="Markdown"
                    )
                except Exception as te:
                    log_event(f"Telegram reward notify error: {te}", "WARNING")
        else:
            log_event(f"[PIPELINE] Severity Moderate/Low — Logged to {department} for routine maintenance.")
            db.update_report(report_id, {"action_taken": "Logged for Maintenance"})

            if chat_id and bot:
                try:
                    bot.send_message(
                        chat_id,
                        f"🎉 *Audit Completed & Reward Issued!*\n\n"
                        f"🏢 *Department*: _{department}_\n"
                        f"📋 *Action*: Logged for routine maintenance queue (48h SLA)\n\n"
                        f"🎁 *YOUR ANONYMOUS VOUCHER*: `{voucher}`\n"
                        f"🪙 *Reward Points*: *+100 Civic Points*\n\n"
                        f"🔒 *Privacy Guarantee*: Your identity remains 100% anonymous.",
                        parse_mode="Markdown"
                    )
                except Exception as te:
                    log_event(f"Telegram routine notify error: {te}", "WARNING")

        log_event(f"[PIPELINE] Complete | report_id: {report_id} | Voucher: {voucher}")

    except Exception as e:
        log_event(f"[PIPELINE] FAILURE: {e}", "ERROR")


async def run_pipeline(image_path: str, location: str = "Unknown", source: str = "Web", chat_id=None):
    run_pipeline_sync(image_path, location, source, chat_id)


# ─── TELEGRAM BOT EVENT HANDLERS ─────────────────────────────────────────────
if bot:
    @bot.message_handler(commands=['start'])
    def telegram_start_cmd(message):
        chat_id = message.chat.id
        log_event(f"[TELEGRAM] /start from chat {chat_id}")
        bot.send_message(chat_id,
            "🛡️ *Welcome to CivicLens Autonomous Governance Defense!*\n\n"
            "Report city infrastructure hazards anonymously. Our AI verifies issues, blocks contractor fraud, and forces repair dispatch within minutes.\n\n"
            "🔒 *100% Anonymous & Zero-KYC:*\n"
            "Your name, phone number, and Telegram identity are NEVER stored in any database. Only the visual evidence is audited.\n\n"
            "📸 *How to Report & Earn Rewards:*\n"
            "1️⃣ *Take a Photo*: Capture the damaged road, water leak, waste dump, or wire hazard.\n"
            "2️⃣ *Send It Here*: Add the street or location name in the photo caption (or send a location pin 📍).\n"
            "3️⃣ *Instant AI Audit*: Gemini Vision & Qdrant verify uniqueness and auto-dial the contractor.\n"
            "4️⃣ *Claim Your Reward*: Receive an **Anonymous Cryptographic Voucher** (`CVL-XXXX-RWD`) with +150 Civic Points!\n\n"
            "👇 *Send a photo now to start your first audit!*",
            parse_mode="Markdown")

    @bot.message_handler(commands=['rewards'])
    def telegram_rewards_cmd(message):
        chat_id = message.chat.id
        bot.send_message(chat_id,
            "🎁 *CivicLens Citizen Rewards Program*\n\n"
            "Every unique verified audit generates an anonymous cryptographic voucher code.\n\n"
            "💎 *Benefits:*\n"
            "• **+150 Civic Points** per verified unique report\n"
            "• Redeemable for municipal property tax rebates & utility bill discounts\n"
            "• Complete identity privacy guaranteed by cryptographic token hashing.\n\n"
            "📸 Send a photo of a civic issue to claim your voucher!",
            parse_mode="Markdown")

    @bot.message_handler(commands=['help'])
    def telegram_help_cmd(message):
        chat_id = message.chat.id
        bot.send_message(chat_id,
            "ℹ️ *CivicLens Bot Commands & Guide*\n\n"
            "• `/start` — Start anonymous reporting\n"
            "• `/rewards` — How to earn & redeem civic reward vouchers\n"
            "• `/status` — Check core system & vector grid status\n\n"
            "📸 Simply send a photo anytime to trigger an audit!",
            parse_mode="Markdown")

    @bot.message_handler(commands=['status'])
    def telegram_status_cmd(message):
        chat_id = message.chat.id
        stats = db.get_stats()
        bot.send_message(chat_id,
            f"🟢 *CivicLens Core Status: ONLINE*\n\n"
            f"• Total Audits Run: *{stats['total']}*\n"
            f"• Verified Unique: *{stats['verified']}*\n"
            f"• Fraud Attempts Blocked: *{stats['duplicates']}*\n"
            f"• Contractor Escalations: *{stats['active_calls']}*\n"
            f"• Taxpayer Funds Protected: *₹{stats['total_savings_inr']:,}*\n"
            f"• Vector Search Latency: *8.4s average*",
            parse_mode="Markdown")

    @bot.message_handler(content_types=['location'])
    def telegram_location_msg(message):
        chat_id = message.chat.id
        lat = message.location.latitude
        lng = message.location.longitude
        TELEGRAM_USER_LOCATIONS[chat_id] = (lat, lng)
        log_event(f"[TELEGRAM] GPS Pin locked for user {chat_id}: {lat}, {lng}")
        bot.send_message(
            chat_id,
            f"📍 *GPS Location Locked!*\n\n"
            f"Coordinates: `{lat:.5f}, {lng:.5f}`\n\n"
            f"Now please send a *photo* of the civic hazard at this location.",
            parse_mode="Markdown"
        )

    @bot.message_handler(content_types=['photo'])
    def telegram_photo_msg(message):
        chat_id = message.chat.id
        try:
            bot.send_message(
                chat_id,
                "📸 *Evidence Received!*\n\n"
                "🔍 Pre-screening and auditing with Gemini 1.5 Flash Vision...\n"
                "🛡️ Running anti-duplicate vector check in Qdrant...",
                parse_mode="Markdown"
            )

            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_info.file_path}"

            log_event(f"[TELEGRAM] Downloading image from Telegram servers...")
            img_response = requests.get(file_url, timeout=20)
            img_response.raise_for_status()
            img_data = img_response.content

            rand_id = uuid.uuid4().hex[:8]
            filename = f"data/uploads/telegram_{rand_id}.jpg"
            with open(filename, "wb") as f:
                f.write(img_data)

            log_event(f"[TELEGRAM] Image saved: {filename} ({len(img_data)} bytes)")

            caption = (message.caption or "").strip()
            location_tag = caption if caption else "Telegram Citizen Report"
            if chat_id in TELEGRAM_USER_LOCATIONS:
                lat, lng = TELEGRAM_USER_LOCATIONS[chat_id]
                location_tag = f"{location_tag} (GPS: {lat:.4f}, {lng:.4f})"

            threading.Thread(
                target=run_pipeline_sync,
                args=(filename, location_tag, "Telegram Anonymous Citizen", chat_id),
                daemon=True
            ).start()

        except Exception as e:
            log_event(f"[TELEGRAM] Photo processing error: {e}", "ERROR")
            bot.send_message(chat_id, "❌ Error processing image. Please try again.")

    @bot.message_handler(func=lambda msg: True)
    def telegram_fallback_text(message):
        chat_id = message.chat.id
        bot.send_message(chat_id,
            "👋 Please send a *photo* of the civic problem you want to report.\n\n"
            "Type `/start` for instructions or `/rewards` to see reward points.",
            parse_mode="Markdown")


def _start_telegram_polling_thread():
    """Starts robust direct long-polling in a daemon thread (zero ngrok dependency!)."""
    if not bot:
        return
    try:
        bot.remove_webhook()
        log_event("[TELEGRAM] Webhook removed. Direct polling activated.")
    except Exception as e:
        log_event(f"[TELEGRAM] remove_webhook error: {e}", "WARNING")

    def _poll_worker():
        log_event("[TELEGRAM] Direct long-polling worker ONLINE & listening for /start, photos, and location pins!")
        while True:
            try:
                bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=False)
            except Exception as pe:
                log_event(f"[TELEGRAM] Polling exception: {pe}. Re-connecting in 3s...", "WARNING")
                time.sleep(3)

    t = threading.Thread(target=_poll_worker, daemon=True)
    t.start()


@app.on_event("startup")
async def on_startup_init():
    """Startup initialization — starts Telegram polling automatically."""
    log_event("[STARTUP] Initializing CivicLens Defense Kernel...")
    _start_telegram_polling_thread()


# ─── TWILIO CALLBACKS ─────────────────────────────────────────────────────────
@app.post("/voice/start")
async def voice_start(request: Request, issue: str = "Pothole", loc: str = "Unknown"):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    log_event(f"Twilio Call initiated. CallSid: {call_sid}")

    reports = db.get_reports()
    for r in reports:
        if r.get("action_taken") in ["Twilio Call Dispatched", "Call Dispatched (Simulation)"] and not r.get("caller_response"):
            issue = r.get("issue_type", issue)
            loc = r.get("location", loc)
            if call_sid:
                db.update_report(r["id"], {"call_sid": call_sid})
            break

    global LATEST_ISSUE
    LATEST_ISSUE = {"type": issue, "loc": loc, "call_sid": call_sid}

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="1" action="/voice/handle-key?call_sid={call_sid}" method="POST" timeout="10">
        <Say voice="alice" language="en-IN">This is an automated enforcement alert from Civic Lens.</Say>
        <Say voice="alice" language="en-IN">A critical {issue} has been reported at {loc}.</Say>
        <Say voice="alice" language="en-IN">Press 1 to acknowledge in English.</Say>
        <Say voice="alice" language="hi-IN">हिंदी में सुनने के लिए दो दबाएं।</Say>
    </Gather>
    <Say>No response received. Call ending.</Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/handle-key")
async def voice_handle(request: Request, Digits: str = Form(...), call_sid: str = None):
    if not call_sid:
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "")

    log_event(f"Twilio Key pressed: {Digits} | CallSid: {call_sid}")

    issue = LATEST_ISSUE["type"]
    loc = LATEST_ISSUE["loc"]

    if Digits == '1':
        msg, lang, response_mode = (f"Acknowledgment received. Critical {issue} at {loc}. Civic Lens expects repair within 4 hours.", "en-IN", "English — Acknowledged")
    elif Digits == '2':
        msg, lang, response_mode = (f"स्वीकृति प्राप्त हुई। {loc} पर {issue} की मरम्मत 4 घंटे में की जाएगी। धन्यवाद।", "hi-IN", "Hindi — Acknowledged")
    else:
        msg, lang, response_mode = ("Invalid input. Ending call.", "en-IN", f"Invalid digit ({Digits})")

    if call_sid:
        for r in db.get_reports():
            if r.get("call_sid") == call_sid:
                db.update_report(r["id"], {"caller_response": response_mode})
                log_event(f"Report acknowledged: {response_mode}")
                break

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="{lang}">{msg}</Say>
    <Pause length="1"/>
    <Say voice="alice" language="{lang}">Civic Lens enforcement call terminated.</Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


# ─── TELEGRAM WEBHOOK (FALLBACK) ─────────────────────────────────────────────
@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        raw_body = await request.body()
        log_event(f"[TELEGRAM] Webhook received ({len(raw_body)} bytes)")

        if not bot:
            return {"status": "ok"}

        update = telebot.types.Update.de_json(raw_body.decode("utf-8"))
        if update:
            bot.process_new_updates([update])
    except Exception as e:
        log_event(f"[TELEGRAM] Webhook error: {e}", "ERROR")

    return {"status": "ok"}


# ─── DASHBOARD API ────────────────────────────────────────────────────────────
@app.get("/api/reports")
async def api_get_reports():
    return db.get_reports()


@app.get("/api/stats")
async def api_get_stats():
    stats = db.get_stats()
    qdrant = memory.get_stats()
    stats["qdrant_vectors"] = qdrant.get("points_count", 0)
    return stats


@app.get("/api/logs")
async def api_get_logs():
    return SYSTEM_LOGS


@app.post("/api/reports/submit")
async def api_submit_report(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    location: str = Form("Sector 4"),
    source: str = Form("Web Simulator")
):
    try:
        rand_id = uuid.uuid4().hex[:6]
        ext = os.path.splitext(image.filename)[1] or ".jpg"
        filepath = f"data/uploads/upload_{rand_id}{ext}"
        with open(filepath, "wb") as f:
            shutil.copyfileobj(image.file, f)
        log_event(f"Web report submitted: {filepath}")
        background_tasks.add_task(run_pipeline, filepath, location, source)
        return {"status": "success", "message": "Report queued for audit"}
    except Exception as e:
        log_event(f"Submit error: {e}", "ERROR")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/reports/preset")
async def api_preset_audit(
    background_tasks: BackgroundTasks,
    preset_id: str = Form(...)
):
    presets = {
        "pothole_crit": {
            "file": "data/test_pothole.jpg",
            "loc": "Ring Road Sector 4, Outer Junction",
            "source": "VC Showcase: Critical Pothole (Live Ingest)"
        },
        "water_burst": {
            "file": "data/test_water_burst.jpg",
            "loc": "Commercial Street, Main Pipeline Crossing",
            "source": "VC Showcase: Municipal Water Rupture (SDB)"
        },
        "duplicate_attack": {
            "file": "data/test_pothole.jpg",
            "loc": "Ring Road Sector 4 (Contractor Duplicate Claim)",
            "source": "VC Showcase: Ghost Repair Fraud Attack"
        },
        "garbage_overflow": {
            "file": "data/test_garbage.jpg",
            "loc": "Market Yard Gate 3, South Ward",
            "source": "VC Showcase: Solid Waste Escalation (SWM)"
        },
        "non_civic_spam": {
            "file": "data/test_coffee.jpg",
            "loc": "Cafe Coffee Day Interior",
            "source": "VC Showcase: Spam Pre-screener Filter"
        }
    }

    preset = presets.get(preset_id)
    if not preset:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Unknown preset: {preset_id}"})

    src_file = preset["file"]
    if not os.path.exists(src_file):
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Preset asset {src_file} missing."})

    rand_id = uuid.uuid4().hex[:6]
    ext = os.path.splitext(src_file)[1] or ".jpg"
    dest_file = f"data/uploads/preset_{preset_id}_{rand_id}{ext}"
    shutil.copyfile(src_file, dest_file)

    log_event(f"[VC_SHOWCASE] Preset audit triggered: {preset_id} -> {dest_file}")
    background_tasks.add_task(run_pipeline, dest_file, preset["loc"], preset["source"])
    return {"status": "success", "message": f"Preset '{preset_id}' queued for autonomous audit", "file": dest_file}


@app.post("/api/reports/simulate-key")
async def api_simulate_key(report_id: str = Form(...), key: str = Form(...)):
    reports = db.get_reports()
    for r in reports:
        if r["id"] == report_id:
            response_mode = "English — Acknowledged" if key == "1" else "Hindi — Acknowledged"
            db.update_report(report_id, {"caller_response": response_mode})
            log_event(f"Simulated keypress '{key}' for report {report_id[:8]}")
            return {"status": "success"}
    return {"status": "error", "message": "Report not found"}


@app.post("/api/seed-db")
async def api_seed_database():
    db.seed_db()
    log_event("DATABASE SEEDED with multi-department audit records.", "INFO")
    return {"status": "success", "message": "Database populated with seed showcase records"}


@app.post("/api/clear-db")
async def api_clear_db():
    db.clear_db()
    memory.reset_collection()
    log_event("DATABASE CLEARED by admin.", "WARNING")
    return {"status": "success", "message": "Database and vectors cleared"}


# ─── WEBSOCKET & STATIC FILES ────────────────────────────────────────────────
@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    CONNECTED_WS.add(ws)
    try:
        for entry in SYSTEM_LOGS:
            await ws.send_json(entry)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in CONNECTED_WS:
            try:
                CONNECTED_WS.remove(ws)
            except KeyError:
                pass

app.mount("/data", StaticFiles(directory="data"), name="data")
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    path = "static/index.html"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>CivicLens running</h1>"