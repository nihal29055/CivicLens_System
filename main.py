import time
import os
import json
import telebot
import requests
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from src.vision_engine import VisionEngine
from src.enforcer_engine import EnforcerEngine
from src.memory_engine import MemoryEngine
from dotenv import load_dotenv

load_dotenv()
console = Console()

# Setup Bot for Polling (No Webhook needed!)
bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))

def main():
    console.clear()
    console.print(Panel("[bold cyan]CIVIC LENS: AUTONOMOUS DEFENSE CORE[/bold cyan]", style="on black"))

    # 1. Initialize Engines
    vision = VisionEngine()
    enforcer = EnforcerEngine()
    memory = MemoryEngine()
    
    # 2. Reset Telegram (Kill old webhooks to allow polling)
    try:
        bot.remove_webhook()
        console.print("[green]✓ Telegram Webhook Removed (Switched to Direct Polling)[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠ Warning: {e}[/yellow]")

    console.print("[green]✓ System Online (Listening for Photos)[/green]")
    
    # 3. THE LISTENER LOOP
    with console.status("[bold yellow]Waiting for Telegram Image...[/bold yellow]") as status:
        found_message = False
        target_file = "data/incoming_telegram.jpg"
        
        while not found_message:
            try:
                # Ask Telegram for updates
                updates = bot.get_updates(offset=-1, timeout=5)
                
                for update in updates:
                    if update.message and update.message.photo:
                        # We found a photo!
                        chat_id = update.message.chat.id
                        
                        # Tell user we got it
                        bot.send_message(chat_id, "🤖 Image Detected. Analyzing severity...")
                        status.update("[green]Packet Detected! Downloading...[/green]")
                        
                        # Download
                        file_id = update.message.photo[-1].file_id
                        file_info = bot.get_file(file_id)
                        file_url = f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/{file_info.file_path}"
                        
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
    console.rule("[bold yellow]EVENT 1: INCOMING TELEGRAM REPORT[/bold yellow]")
    
    # Analyze
    console.print("[dim]> Gemini Flash: Analyzing Severity...[/dim]")
    analysis = vision.analyze_image(target_file, mode="severity")
    console.print(f"[white]Issue: {analysis.get('issue_type')} | Severity: {analysis.get('severity')}[/white]")

    # Vectorize
    console.print("[dim]> Qdrant: Vectorizing & Indexing Evidence...[/dim]")
    vector = vision.get_embedding(str(analysis))
    memory.save_record(vector, {"type": "telegram_report", "data": analysis})
    console.print("[green]✓ Evidence Secured in Vector DB[/green]")

    # 5. THE CALL
    if analysis.get('severity') == "Critical":
        console.print("\n[red]>> SEVERITY CRITICAL. DIALING CONTRACTOR...[/red]")
        
        # Trigger IVR (Still needs Server running for the TwiML)
        call_sid = enforcer.trigger_ivr_call(analysis.get('issue_type'), "Sector 4")
        
        if "SIMULATION" not in str(call_sid):
            console.print(f"[green]✓ CALL CONNECTED (SID: {call_sid})[/green]")
            console.print("[yellow]>> LISTENING FOR INPUT (Press 1 or 2)...[/yellow]")
        else:
            console.print("[red]!! CALL FAILED: CHECK NGROK URL IN .ENV !![/red]")

    console.print("\n[bold green]DEMO COMPLETE[/bold green]")

if __name__ == "__main__":
    main()