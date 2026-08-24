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
    # Send the entry to all connected WS clients; remove disconnected sockets
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
    # Broadcast asynchronously to connected websocket clients (fire-and-forget)
    try:
        asyncio.create_task(_broadcast_log(entry))
    except Exception:
        pass

log_event("CivicLens Server starting up...")

# Telegram Bot setup
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
NGROK_URL = os.getenv("NGROK_URL", "").strip()
bot = None
if TELEGRAM_BOT_TOKEN:
    try:
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        log_event(f"Telegram Bot initialized OK.")
    except Exception as e:
        log_event(f"Telegram Bot init FAILED: {e}", "ERROR")
else:
    log_event("No TELEGRAM_BOT_TOKEN found in .env", "WARNING")


@app.on_event("startup")
async def register_telegram_webhook():
    """Auto-register the Telegram webhook on server startup."""
    # Re-read env directly in case module-level vars are stale after reload
    from dotenv import load_dotenv as _load
    _load(override=True)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    ngrok = os.getenv("NGROK_URL", "").strip()
    log_event(f"[TELEGRAM] Startup: token length={len(token)}, ngrok={ngrok}")

    if not token:
        log_event("[TELEGRAM] Skipping webhook registration — no token.", "WARNING")
        return
    if not ngrok:
        log_event("[TELEGRAM] Skipping webhook registration — NGROK_URL not set in .env.", "WARNING")
        return
    webhook_url = f"{ngrok}/telegram-webhook"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]},
            timeout=10
        )
        result = resp.json()
        if result.get("ok"):
            log_event(f"[TELEGRAM] Webhook registered: {webhook_url}")
        else:
            log_event(f"[TELEGRAM] Webhook registration failed: {result}", "ERROR")
    except Exception as e:
        log_event(f"[TELEGRAM] Webhook registration error: {e}", "ERROR")

LATEST_ISSUE = {"type": "Pothole", "loc": "Sector 4", "call_sid": ""}


# ─── CORE PIPELINE ───────────────────────────────────────────────────────────
async def run_pipeline(image_path: str, location: str = "Unknown", source: str = "Web", chat_id=None):
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
            # Notify the Telegram reporter
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
            # Clean up the saved file since it's invalid
            try:
                os.remove(image_path)
            except Exception:
                pass
            return  # Stop pipeline here — no DB entry for invalid images

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

        db.update_report(report_id, {"issue_type": issue_type, "severity": severity, "desc": desc})

        # ── Step 2: Qdrant Duplicate Check ────────────────────────────────
        log_event("[PIPELINE] Vectorizing evidence fingerprint...")
        vector = vision.get_embedding(visual_fingerprint)

        log_event("[PIPELINE] Querying Qdrant Vector DB for fraud/duplicate check...")
        is_duplicate, score, _ = memory.search_duplicate(vector)

        if is_duplicate:
            log_event(f"FRAUD DETECTED! Duplicate evidence score: {score*100:.1f}%", "WARNING")
            db.update_report(report_id, {
                "status": "Duplicate Fraud",
                "duplicate_score": float(score),
                "action_taken": "Blocked (Duplicate Fraud)"
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
        log_event("[PIPELINE] Evidence unique. Saving to Qdrant...")
        memory.save_record(vector, {"report_id": report_id, "issue_type": issue_type, "location": location})
        db.update_report(report_id, {"status": "Verified"})

        if chat_id and bot:
            try:
                bot.send_message(chat_id,
                    f"✅ *Report Verified!*\n\n"
                    f"Issue: *{issue_type}*\n"
                    f"Severity: *{severity}*\n"
                    f"Location: {location}\n\n"
                    f"{desc}\n\n"
                    f"Notifying the responsible contractor now...",
                    parse_mode="Markdown")
            except Exception as te:
                log_event(f"Telegram verified reply error: {te}", "WARNING")

        # ── Step 4: Twilio IVR Call ───────────────────────────────────────
        if severity == "Critical":
            log_event("[PIPELINE] CRITICAL severity — Initiating Twilio IVR call...")
            call_sid = enforcer.trigger_ivr_call(issue_type, location)
            action = "Call Dispatched (Simulation)" if "SIMULATION" in str(call_sid) else "Twilio Call Dispatched"
            log_event(f"[PIPELINE] Call result: {action} | SID: {call_sid}")
            db.update_report(report_id, {"action_taken": action, "call_sid": call_sid})

            if chat_id and bot and "SIMULATION" not in str(call_sid):
                try:
                    bot.send_message(chat_id, "📞 Contractor has been called via automated IVR alert.")
                except:
                    pass
        else:
            log_event("[PIPELINE] Severity Moderate/Low — Logged for routine maintenance.")
            db.update_report(report_id, {"action_taken": "Logged for Maintenance"})

        log_event(f"[PIPELINE] Complete | report_id: {report_id}")

    except Exception as e:
        log_event(f"[PIPELINE] FAILURE: {e}", "ERROR")


# ─── TWILIO CALLBACKS ─────────────────────────────────────────────────────────
@app.post("/voice/start")
async def voice_start(request: Request, issue: str = "Pothole", loc: str = "Unknown"):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    log_event(f"Twilio Call initiated. CallSid: {call_sid}")

    # Match report to this call
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


# ─── TELEGRAM WEBHOOK ─────────────────────────────────────────────────────────
@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        raw_body = await request.body()
        log_event(f"[TELEGRAM] Webhook received ({len(raw_body)} bytes)")

        if not bot:
            log_event("[TELEGRAM] ERROR: Bot not initialized. Check TELEGRAM_BOT_TOKEN in .env", "ERROR")
            return {"status": "ok"}

        update = telebot.types.Update.de_json(raw_body.decode("utf-8"))

        if not update or not update.message:
            log_event("[TELEGRAM] No message in update — ignoring", "WARNING")
            return {"status": "ok"}

        chat_id = update.message.chat.id
        log_event(f"[TELEGRAM] Message received (type: {'photo' if update.message.photo else 'text'})")

        # ── Photo message ──────────────────────────────────────────────────
        if update.message.photo:
            try:
                bot.send_message(chat_id, "📸 Image received! Checking if this is a valid civic issue...")
            except Exception as e:
                log_event(f"[TELEGRAM] Ack send failed: {e}", "WARNING")

            try:
                file_id = update.message.photo[-1].file_id
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

                # Use caption as location if provided
                caption = (update.message.caption or "").strip()
                location_tag = caption if caption else "Telegram Report (Location not provided)"

                background_tasks.add_task(run_pipeline, filename, location_tag, "Telegram Bot", chat_id)

            except Exception as e:
                log_event(f"[TELEGRAM] Image processing error: {e}", "ERROR")
                try:
                    bot.send_message(chat_id, "❌ Failed to process your image. Please try again with a clear photo.")
                except:
                    pass

        # ── Text message ──────────────────────────────────────────────────
        elif update.message.text:
            text = update.message.text.strip()
            log_event(f"[TELEGRAM] Text: {text[:60]}")

            try:
                command = text.split()[0].lower().split('@', 1)[0] if text else ""
                if command in ["/start", "/help"]:
                    bot.send_message(chat_id,
                        "👋 *Welcome to CivicLens!*\n\n"
                        "I help report civic issues to authorities anonymously.\n\n"
                        "📸 *How to report an issue:*\n"
                        "1. Take a clear photo of the civic problem\n"
                        "2. Send the photo to me\n"
                        "3. Add a *caption* with the location (optional)\n"
                        "   e.g. _'MG Road near bus stop'_\n\n"
                        "Our AI will:\n"
                        "• Analyze the issue type\n"
                        "• Check for duplicate reports\n"
                        "• Call the responsible contractor\n\n"
                        "Supported issues: Pothole, Leaking Pipe, Broken Streetlight, Drainage Overflow, Garbage Dumping & more.",
                        parse_mode="Markdown")
                else:
                    bot.send_message(chat_id,
                        "Please send a *photo* of the civic issue.\n"
                        "Type /help to see instructions.",
                        parse_mode="Markdown")
            except Exception as e:
                log_event(f"[TELEGRAM] Text reply error: {e}", "WARNING")

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


@app.post("/api/clear-db")
async def api_clear_db():
    """Admin endpoint — wipes all reports and Qdrant vectors."""
    db.clear_db()
    memory.reset_collection()
    log_event("DATABASE CLEARED by admin.", "WARNING")
    return {"status": "success", "message": "Database and vectors cleared"}


# ─── STATIC FILES ─────────────────────────────────────────────────────────────
@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    CONNECTED_WS.add(ws)
    try:
        # send backlog on connect
        for entry in SYSTEM_LOGS:
            await ws.send_json(entry)
        while True:
            # keep connection alive — clients may send pings
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