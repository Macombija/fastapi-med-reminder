# main.py  (FastAPI Med-Reminder – SPARL SMTP edition)
import os
import smtplib
import ssl
import threading
import time
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import schedule

# ---------- configuration ----------
load_dotenv()  # pulls vars from .env

SMTP_HOST = os.getenv("SMTP_HOST", "mail.sparl.co.ke")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")  # renhard.miyoma@sparl.co.ke
SMTP_PASS = os.getenv("SMTP_PASS")  # your e-mail password
FROM_EMAIL = SMTP_USER  # must match authenticated user

# ---------- FastAPI ----------
app = FastAPI(title="Med-Reminder API (SPARL SMTP)", version="1.0.0")

# ---------- models ----------
class ReminderRequest(BaseModel):
    email: EmailStr
    medication: str

# ---------- in-memory store ----------
jobs: Dict[str, dict] = {}  # {job_id: {"email": ..., "drug": ..., "active": True}}

# ---------- e-mail helper ----------
def send_email(to_email: str, drug: str, job_id: str) -> None:
    if not jobs[job_id]["active"]:
        return  # job was stopped

    msg = EmailMessage()
    msg["Subject"] = f"Time for your {drug}"
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    stop_url = f"http://127.0.0.1:8000/stop/{job_id}"
    msg.set_content(
        f"Hi!\n\nPlease take your {drug}.\n\n"
        f"Click here to stop reminders: {stop_url}"
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

    print(f"[{datetime.now(timezone.utc)}] reminder sent to {to_email}")

# ---------- scheduler thread ----------
def run_scheduler() -> None:
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_scheduler, daemon=True).start()

# ---------- API endpoints ----------
@app.post("/schedule")
def schedule_reminder(body: ReminderRequest):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"email": body.email, "drug": body.medication, "active": True}

    # schedule every 5 min (first trigger happens immediately)
    schedule.every(5).minutes.do(send_email, body.email, body.medication, job_id)
    return {
        "message": "Reminder scheduled",
        "job_id": job_id,
        "stop_url": f"/stop/{job_id}",
    }

@app.get("/stop/{job_id}")
def stop_reminder(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Unknown job")
    jobs[job_id]["active"] = False
    return {"message": "Reminders stopped"}

# ---------- root ----------
@app.get("/")
def read_root():
    return {"info": "Visit /docs to interact with the API"}