import time
import os
import json
import telebot
import requests
import uuid
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from src.vision_engine import VisionEngine
from src.enforcer_engine import EnforcerEngine
from src.memory_engine import MemoryEngine
import src.db as db
from dotenv import load_dotenv

load_dotenv()
console = Console()

# Setup Bot for Polling (No Webhook needed!)
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
bot = None
if bot_token:
    try:
        bot = telebot.TeleBot(bot_token)
    except Exception as e:
        console.print(f"[red]Failed to initialize Telegram Bot: {e}[/red]")

def main():
    console.clear()
    console.print(Panel("[bold cyan]CIVIC LENS: AUTONOMOUS DEFENSE CORE CLI[/bold cyan]", style="on black"))

    # 1. Initialize Engines
    vision = VisionEngine()
    enforcer = EnforcerEngine()
    memory = MemoryEngine()
    
    # 2. Reset Telegram (Kill old webhooks to allow polling)
    if bot:
        try:
            bot.remove_webhook()
            console.print("[green]✓ Telegram Webhook Removed (Switched to Direct Polling)[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Warning removing webhook: {e}[/yellow]")

    console.print("[green]✓ System Online (Listening for Photos)[/green]")
    
    # 3. THE LISTENER LOOP
    target_file = "data/incoming_telegram.jpg"
    os.makedirs("data", exist_ok=True)
    
    # Check if we should run in mock loop if no telegram token is set
    if not bot:
        console.print("[yellow]⚠ TELEGRAM_BOT_TOKEN not found in .env. Checking for mock triggers...[/yellow]")
        console.print("[yellow]Hint: Send an image manually or run backend server.py for Dashboard simulator.[/yellow]")
        
        # In mock mode, we wait for a local file to appear
        mock_file = "data/mock_telegram.jpg"
        if not os.path.exists(mock_file) and os.path.exists("data/test_pothole.jpg"):
            # Copy test_pothole to mock_telegram to start automatically if it doesn't exist
            shutil_path = "data/test_pothole.jpg"
            console.print(f"[dim]Copying {shutil_path} to {mock_file} for local CLI demo simulation...[/dim]")
            import shutil
            shutil.copy(shutil_path, mock_file)
            
        with console.status("[bold yellow]Waiting for local trigger file (data/mock_telegram.jpg)...[/bold yellow]") as status:
            while not os.path.exists(mock_file):
                time.sleep(1)
            
            status.update("[green]Trigger file detected! Copying to processing file...[/green]")
            time.sleep(1)
            # Copy to target file
            import shutil
            shutil.copy(mock_file, target_file)
            # Remove mock trigger so we don't loop endlessly
            try:
                os.remove(mock_file)
            except:
                pass
            
            chat_id = 99999999
            source = "CLI Mock Simulator"
            console.print(f"[green]✓ Loaded local trigger: {target_file}[/green]")
    else:
        with console.status("[bold yellow]Waiting for Telegram Image...[/bold yellow]") as status:
            found_message = False
            while not found_message:
                try:
                    # Ask Telegram for updates
                    updates = bot.get_updates(offset=-1, timeout=5)
                    
                    for update in updates:
                        if update.message and update.message.photo:
                            # We found a photo!
                            chat_id = update.message.chat.id
                            source = f"Telegram User ({chat_id})"
                            
                            # Tell user we got it
                            bot.send_message(chat_id, "🤖 Image Detected. Analyzing severity and checking database...")
                            status.update("[green]Packet Detected! Downloading...[/green]")
                            
                            # Download
                            file_id = update.message.photo[-1].file_id
                            file_info = bot.get_file(file_id)
                            file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_info.file_path}"
                            
                            img_data = requests.get(file_url).content
                            with open(target_file, "wb") as f:
                                f.write(img_data)
                            
                            found_message = True
                            break # Exit the loop
                    time.sleep(1)
                except Exception as e:
                    # Ignore network blips
                    pass

    # 4. PROCESSING (The Demo Continues)
    console.rule("[bold yellow]EVENT 1: INCOMING REPORT PROCESSING[/bold yellow]")
    
    # Save a temporary report entry in the shared database
    report_id = str(uuid.uuid4())
    # Save the file uniquely in data/uploads so the dashboard can render it
    os.makedirs("data/uploads", exist_ok=True)
    stored_filename = f"data/uploads/cli_{uuid.uuid4().hex[:8]}.jpg"
    import shutil
    shutil.copy(target_file, stored_filename)
    
    rel_img_path = f"/data/uploads/{os.path.basename(stored_filename)}"
    report = {
        "id": report_id,
        "timestamp": datetime.now().isoformat(),
        "image_path": rel_img_path,
        "location": "Sector 4 (CLI)",
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

    # Analyze
    console.print("[dim]> Gemini Flash: Analyzing Severity...[/dim]")
    analysis = vision.analyze_image(stored_filename, mode="severity")
    
    issue_type = analysis.get("issue_type", "Pothole")
    severity = analysis.get("severity", "Critical")
    desc = analysis.get("desc", "Visual damage detected")
    visual_fingerprint = analysis.get("visual_fingerprint", "")
    
    console.print(f"[white]Issue: {issue_type} | Severity: {severity}[/white]")
    console.print(f"[dim]Visual fingerprint: {visual_fingerprint[:100]}...[/dim]")

    db.update_report(report_id, {
        "issue_type": issue_type,
        "severity": severity,
        "desc": desc
    })

    # Vectorize
    console.print("[dim]> Qdrant: Vectorizing & Checking Duplicates...[/dim]")
    vector = vision.get_embedding(visual_fingerprint or desc)
    
    is_duplicate, score, matching_payload = memory.search_duplicate(vector)
    
    if is_duplicate:
        console.print(Panel(
            f"[bold red]❌ DUPLICATE FRAUD DETECTED (Similarity: {score*100:.1f}%)[/bold red]\n"
            f"[yellow]Blocked Payment & Banned Recycled Evidence.[/yellow]\n"
            f"Matching Database ID: {matching_payload.get('report_id') if matching_payload else 'Unknown'}",
            title="Governance Core Alert", border_style="red"
        ))
        
        db.update_report(report_id, {
            "status": "Duplicate Fraud",
            "duplicate_score": float(score),
            "action_taken": "Blocked (Duplicate Fraud)"
        })
        
        if bot and chat_id != 99999999:
            try:
                bot.send_message(chat_id, f"❌ FRAUD ALERT: Duplicate evidence detected ({score*100:.1f}% match). Audit blocked, payment frozen.")
            except:
                pass
        return

    # If unique, save and continue
    console.print("[green]✓ Evidence Unique. Securing record in Qdrant Vector Grid[/green]")
    memory.save_record(vector, {
        "report_id": report_id,
        "issue_type": issue_type,
        "location": "Sector 4 (CLI)",
        "visual_fingerprint": visual_fingerprint
    })
    
    db.update_report(report_id, {"status": "Verified"})
    
    if bot and chat_id != 99999999:
        try:
            bot.send_message(chat_id, "✓ Evidence secured in Qdrant. Auditing severity...")
        except:
            pass

    # 5. THE CALL
    if severity == "Critical":
        console.print("\n[red]>> SEVERITY CRITICAL. DIALING CONTRACTOR ESCALATION...[/red]")
        
        # Trigger IVR (Still needs Server running for the TwiML)
        call_sid = enforcer.trigger_ivr_call(issue_type, "Sector 4")
        
        action_taken = "Twilio Call Dispatched"
        if "SIMULATION" not in str(call_sid):
            console.print(f"[green]✓ CALL CONNECTED (SID: {call_sid})[/green]")
            console.print("[yellow]>> LISTENING FOR INPUT ON SERVER CALLBACKS...[/yellow]")
        else:
            console.print(f"[yellow]⚠ Call running in SIMULATION mode (SID: {call_sid})[/yellow]")
            action_taken = "Call Dispatched (Simulation)"
            
        db.update_report(report_id, {
            "action_taken": action_taken,
            "call_sid": call_sid
        })
        
        if bot and chat_id != 99999999:
            try:
                bot.send_message(chat_id, f"📞 Escalated: contractor call placed (SID: {call_sid})")
            except:
                pass
    else:
        console.print("\n[green]✓ Severity Level Low/Moderate. Logged for standard routing.[/green]")
        db.update_report(report_id, {
            "action_taken": "Logged for Maintenance"
        })

    console.print("\n[bold green]DEMO COMPLETE[/bold green]")

if __name__ == "__main__":
    main()