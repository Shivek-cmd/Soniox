import os

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_NUMBER = os.environ["TWILIO_NUMBER"]
YOUR_NUMBER = os.environ["YOUR_NUMBER"]

NGROK_URL = os.environ["NGROK_URL"]

client = Client(ACCOUNT_SID, AUTH_TOKEN)

call = client.calls.create(
    url=f"{NGROK_URL}/incoming-call",
    to=YOUR_NUMBER,
    from_=TWILIO_NUMBER,
)

print(f"Call started: {call.sid}")
