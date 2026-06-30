from twilio.rest import Client
import telebot
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class EnforcerEngine:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_num = os.getenv("TWILIO_FROM_NUMBER")
        self.target_num = os.getenv("TARGET_PHONE_NUMBER")
        
        raw_url = os.getenv("NGROK_URL", "")
        self.ngrok_url = raw_url.rstrip("/")

        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.bot = None
        if self.bot_token:
            try:
                self.bot = telebot.TeleBot(self.bot_token)
            except Exception as e:
                print(f">> TELEGRAM BOT INIT ERROR: {e}")

        # Initialize Twilio Client safely
        self.client = None
        self.simulation_mode = True
        if self.account_sid and self.auth_token and self.from_num and self.target_num:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                self.simulation_mode = False
                print(">> ENFORCER ENGINE: Twilio Client initialized successfully.")
            except Exception as e:
                print(f">> WARNING: Twilio Client initialization failed ({e}). Running in SIMULATION MODE.")
        else:
            print(">> ENFORCER ENGINE: Missing Twilio credentials. Running in SIMULATION MODE.")

    def trigger_ivr_call(self, issue_type, location):
        """
        Initiates the IVR call to the contractor.
        Encodes URL parameters to prevent Twilio errors.
        """
        safe_issue = urllib.parse.quote(issue_type)
        safe_loc = urllib.parse.quote(location)
        
        url = f"{self.ngrok_url}/voice/start?issue={safe_issue}&loc={safe_loc}"
        
        print(f">> DIALING URL: {url}")
        
        if self.simulation_mode or not self.client:
            print(f">> SIMULATION CALL: Dialing contractor at {self.target_num or '+919999999999'} for '{issue_type}' at '{location}'")
            import uuid
            return f"SIMULATION_CALL_{uuid.uuid4().hex[:8]}"
        
        try:
            call = self.client.calls.create(
                to=self.target_num,
                from_=self.from_num,
                url=url
            )
            return call.sid
        except Exception as e:
            print(f"!! CALL FAILED: {e}")
            import uuid
            return f"SIMULATION_CALL_{uuid.uuid4().hex[:8]}"

    def send_telegram_msg(self, chat_id, text):
        if self.bot:
            try:
                self.bot.send_message(chat_id, text)
            except Exception as e:
                print(f"!! TELEGRAM MSG FAILED: {e}")