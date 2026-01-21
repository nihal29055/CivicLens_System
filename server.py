from fastapi import FastAPI, Request, Form
from fastapi.responses import Response
from src.vision_engine import VisionEngine
from src.enforcer_engine import EnforcerEngine
from src.memory_engine import MemoryEngine
import telebot
import os
import requests
import json
import time

app = FastAPI()
vision = VisionEngine()
enforcer = EnforcerEngine()
memory = MemoryEngine()

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))

# Global State
LATEST_ISSUE = {"type": "Damage", "loc": "City Center"}

# ---------------------------------------------------------
# 📞 1. THE CALL MENU (IVR)
# ---------------------------------------------------------
@app.post("/voice/start")
async def voice_start(issue: str = "Damage", loc: str = "City"):
    global LATEST_ISSUE
    LATEST_ISSUE = {"type": issue, "loc": loc}
    
    twiml = f"""
    <Response>
        <Gather numDigits="1" action="/voice/handle-key" method="POST" timeout="10">
            <Say voice="alice" language="en-IN">Civic Lens Emergency.</Say>
            <Say voice="alice" language="en-IN">Press 1 for English.</Say>
            <Say voice="alice" language="hi-IN">Hindi ke liye 2 dabayein.</Say>
            <Say voice="alice" language="en-IN">Press 6 for Main Menu.</Say>
        </Gather>
        <Say>No input. Goodbye.</Say>
    </Response>
    """
    return Response(content=twiml, media_type="application/xml")

@app.post("/voice/handle-key")
async def voice_handle(Digits: str = Form(...)):
    issue = LATEST_ISSUE["type"]
    loc = LATEST_ISSUE["loc"]
    
    if Digits == '1':
        msg = f"Warning. Critical {issue} reported at {loc}. Repair immediately."
        lang = "en-IN"
    elif Digits == '2':
        msg = f"Saavdhan. {loc} par gambhir {issue} paya gaya hai."
        lang = "hi-IN"
    else:
        msg = "Returning to Main Menu."
        lang = "en-IN"

    twiml = f"""
    <Response>
        <Say voice="alice" language="{lang}">{msg}</Say>
    </Response>
    """
    return Response(content=twiml, media_type="application/xml")

# ---------------------------------------------------------
# 🤖 2. TELEGRAM HANDLER (Robust)
# ---------------------------------------------------------
@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        json_str = await request.json()
        update = telebot.types.Update.de_json(json_str)
        
        if update.message and update.message.photo:
            chat_id = update.message.chat.id
            
            # 1. Download Photo
            file_id = update.message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/{file_info.file_path}"
            
            img_data = requests.get(file_url).content
            
            # Ensure directory exists
            os.makedirs("data", exist_ok=True)
            
            # Save Image (Flush to ensure it exists)
            filename = "data/incoming_telegram.jpg"
            with open(filename, "wb") as f:
                f.write(img_data)
                f.flush()
                os.fsync(f.fileno()) 
            
            # 2. CREATE SIGNAL FILE (Only after image is safe)
            with open("data/trigger.json", "w") as f:
                json.dump({"source": "telegram", "chat_id": chat_id}, f)
                f.flush()
                os.fsync(f.fileno())

            # 3. Reply to User
            bot.send_message(chat_id, "Image Received. Waking up Defense Core...")
            
    except Exception as e:
        print(f"!! WEBHOOK ERROR: {e}")
            
    return {"status": "ok"}