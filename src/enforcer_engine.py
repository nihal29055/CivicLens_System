# from twilio.rest import Client
# import os
# from dotenv import load_dotenv

# load_dotenv()

# class EnforcerEngine:
#     def __init__(self):
#         self.client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
#         self.from_num = os.getenv("TWILIO_FROM_NUMBER") # Can be same for Voice & WhatsApp (if configured)
#         self.target_num = os.getenv("TARGET_PHONE_NUMBER")

#     def call_contractor(self, issue_type, location, language="en-IN"):
#         """
#         Triggers the AI Bureaucrat Call.
#         language options: 'en-IN' (Indian English), 'hi-IN' (Hindi)
#         """
        
#         # ---------------------------------------------------------
#         # 📝 EDIT YOUR 20+ SECOND SCRIPT HERE
#         # ---------------------------------------------------------
#         if language == "hi-IN":
#             # Hindi Script
#             message_body = f"""
#             Namaskar. Yeh Civic Lens Government Audit System hai.
#             <Pause length="1"/>
#             Humein {location} par ek gambhir {issue_type} ki shikayat mili hai.
#             <Pause length="1"/>
#             Yeh ek aakhri chetavni hai. Yadi 24 ghante ke bhitar kaam shuru nahi hua, to aapka contract hold par rakha jayega.
#             <Pause length="1"/>
#             Kripya turant action lein. Dhanyavad.
#             """
#         else:
#             # English Script (20+ Seconds)
#             message_body = f"""
#             Attention. This is an automated enforcement call from the Civic Lens Municipal Oversight System.
#             <Pause length="1"/>
#             We have received verified visual evidence of a critical infrastructure failure.
#             <Pause length="1"/>
#             Issue Type: {issue_type}.
#             Location: {location}.
#             <Pause length="1"/>
#             Our AI Audit Core has flagged this as a Priority One violation. 
#             <Pause length="1"/>
#             You have exactly 4 hours to deploy a repair team before we initiate a payment freeze protocol and blacklist your agency.
#             <Pause length="1"/>
#             Upload geotagged proof of repair to the portal immediately. This is your final warning.
#             """
#         # ---------------------------------------------------------

#         twiml = f"""
#         <Response>
#             <Say voice="alice" language="{language}">{message_body}</Say>
#         </Response>
#         """
        
#         try:
#             call = self.client.calls.create(
#                 twiml=twiml,
#                 to=self.target_num,
#                 from_=self.from_num
#             )
#             return call.sid
#         except Exception as e:
#             print(f"!! CALL FAILED: {e}")
#             return "SIMULATION_ID_123"

#     def send_whatsapp(self, to_number, message_body):
#         """
#         Sends WhatsApp message. 
#         NOTE: For Twilio Sandbox, 'to_number' must be 'whatsapp:+91...'
#         """
#         try:
#             # Ensure numbers have 'whatsapp:' prefix
#             sender = f"whatsapp:{self.from_num}" if not self.from_num.startswith("whatsapp:") else self.from_num
#             receiver = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
            
#             msg = self.client.messages.create(
#                 from_=sender,
#                 body=message_body,
#                 to=receiver
#             )
#             return msg.sid
#         except Exception as e:
#             print(f"!! WHATSAPP FAILED: {e}")
#             return None


from twilio.rest import Client
import telebot
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class EnforcerEngine:
    def __init__(self):
        self.client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.from_num = os.getenv("TWILIO_FROM_NUMBER")
        self.target_num = os.getenv("TARGET_PHONE_NUMBER")
        
        # Remove any trailing slash from Ngrok URL just in case
        raw_url = os.getenv("NGROK_URL", "")
        self.ngrok_url = raw_url.rstrip("/")

        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.bot = None
        if self.bot_token:
            self.bot = telebot.TeleBot(self.bot_token)

    def trigger_ivr_call(self, issue_type, location):
        """
        Initiates the call. Encodes URL parameters to prevent Twilio errors.
        """
        # SAFE URL ENCODING (Fixes the "Sector 4" space error)
        safe_issue = urllib.parse.quote(issue_type)
        safe_loc = urllib.parse.quote(location)
        
        url = f"{self.ngrok_url}/voice/start?issue={safe_issue}&loc={safe_loc}"
        
        print(f">> DIALING URL: {url}") # Debug print
        
        try:
            call = self.client.calls.create(
                to=self.target_num,
                from_=self.from_num,
                url=url
            )
            return call.sid
        except Exception as e:
            print(f"!! CALL FAILED: {e}")
            return "SIMULATION_MODE"

    def send_telegram_msg(self, chat_id, text):
        if self.bot:
            try:
                self.bot.send_message(chat_id, text)
            except:
                pass