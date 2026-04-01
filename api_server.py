#!/usr/bin/env python3
"""MarxStein Group — Backend API with user auth, bookings, contact, and admin."""
import smtplib, ssl, json, hashlib, secrets, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

# ─── Database ───
DB_PATH = "marxstein.db"

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT DEFAULT '',
            password_hash TEXT NOT NULL, preferred_pickup TEXT DEFAULT '', preferred_vehicle TEXT DEFAULT '',
            role TEXT DEFAULT 'user', created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT, name TEXT, email TEXT, pickup TEXT, vehicle TEXT, days TEXT,
            service TEXT, total TEXT, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # Create admin if not exists
    admin = db.execute("SELECT id FROM users WHERE role='admin'").fetchone()
    if not admin:
        h = hashlib.sha256("MarxStein2024!".encode()).hexdigest()
        db.execute("INSERT OR IGNORE INTO users (name,email,phone,password_hash,role) VALUES (?,?,?,?,?)",
                   ("Admin","admin@marxstein.com","",h,"admin"))
    db.commit()
    db.close()

init_db()

# ─── SMTP ───
SMTP_HOST = "mail.euroafricalink24.com"
SMTP_PORT = 465
SMTP_USER = "info@euroafricalink24.com"
SMTP_PASS = "KaylaKelyn2015?"
COMPANY_EMAIL = "contact@marxstein.com"

def send_email(to, subject, html_body, reply_to=None):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"MarxStein Group <{SMTP_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to: msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html_body, "html"))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

# ─── App ───
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── Models ───
class RegisterReq(BaseModel):
    name: str; email: str; phone: str = ""; password: str

class LoginReq(BaseModel):
    email: str; password: str

class ProfileReq(BaseModel):
    email: str; name: str; phone: str = ""; preferred_pickup: str = ""; preferred_vehicle: str = ""

class BookingReq(BaseModel):
    name: str; email: str; pickup: str; vehicle: str; days: str; service: str; total: str; lang: str = "en"

class ContactReq(BaseModel):
    name: str; email: str; phone: str = ""; subject: str = ""; message: str; lang: str = "en"

# ─── Auth Endpoints ───
@app.post("/api/register")
async def register(d: RegisterReq):
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email=?", (d.email,)).fetchone()
    if existing:
        db.close()
        return JSONResponse(status_code=400, content={"error": "Email already registered"})
    h = hashlib.sha256(d.password.encode()).hexdigest()
    db.execute("INSERT INTO users (name,email,phone,password_hash) VALUES (?,?,?,?)", (d.name, d.email, d.phone, h))
    db.commit()
    db.close()
    return {"success": True, "user": {"name": d.name, "email": d.email, "phone": d.phone, "role": "user"}}

@app.post("/api/login")
async def login(d: LoginReq):
    db = get_db()
    h = hashlib.sha256(d.password.encode()).hexdigest()
    user = db.execute("SELECT name,email,phone,role,preferred_pickup,preferred_vehicle FROM users WHERE email=? AND password_hash=?", (d.email, h)).fetchone()
    db.close()
    if not user:
        return JSONResponse(status_code=401, content={"error": "Invalid email or password"})
    return {"success": True, "user": dict(user)}

@app.post("/api/profile")
async def update_profile(d: ProfileReq):
    db = get_db()
    db.execute("UPDATE users SET name=?, phone=?, preferred_pickup=?, preferred_vehicle=? WHERE email=?",
               (d.name, d.phone, d.preferred_pickup, d.preferred_vehicle, d.email))
    db.commit()
    db.close()
    return {"success": True}

# ─── Booking ───
@app.post("/api/booking")
async def booking(d: BookingReq):
    db = get_db()
    db.execute("INSERT INTO bookings (user_email,name,email,pickup,vehicle,days,service,total) VALUES (?,?,?,?,?,?,?,?)",
               (d.email, d.name, d.email, d.pickup, d.vehicle, d.days, d.service, d.total))
    db.commit()
    db.close()
    now = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    company_html = f"""<div style="font-family:Arial;max-width:600px;margin:0 auto;">
      <div style="background:#4B2D7F;padding:20px 24px;border-radius:12px 12px 0 0;"><h2 style="color:#fff;margin:0;">New Booking</h2><p style="color:rgba(255,255,255,.8);font-size:14px;margin:4px 0 0;">MarxStein Group — {now}</p></div>
      <div style="background:#fff;padding:24px;border:1px solid #e8e8e8;border-radius:0 0 12px 12px;"><table style="width:100%;font-size:14px;">
        <tr><td style="padding:8px 0;color:#888;width:120px;">Name</td><td style="font-weight:600;">{d.name}</td></tr>
        <tr><td style="padding:8px 0;color:#888;">Email</td><td><a href="mailto:{d.email}">{d.email}</a></td></tr>
        <tr><td style="padding:8px 0;color:#888;">Pickup</td><td>{d.pickup}</td></tr>
        <tr><td style="padding:8px 0;color:#888;">Vehicle</td><td style="font-weight:600;">{d.vehicle}</td></tr>
        <tr><td style="padding:8px 0;color:#888;">Days</td><td>{d.days}</td></tr>
        <tr><td style="padding:8px 0;color:#888;">Service</td><td>{d.service}</td></tr>
        <tr><td style="padding:8px 0;color:#888;">Total</td><td style="font-weight:700;font-size:16px;">{d.total}</td></tr>
      </table></div></div>"""
    try: send_email(COMPANY_EMAIL, f"Booking from {d.name} — {d.vehicle}", company_html, reply_to=d.email)
    except: pass
    try:
        is_fr = d.lang == "fr"
        send_email(d.email, ("Votre réservation — MarxStein Group" if is_fr else "Your booking — MarxStein Group"),
            f"<div style='font-family:Arial;max-width:600px;margin:0 auto;'><div style='background:#4B2D7F;padding:20px;border-radius:12px 12px 0 0;text-align:center;'><h2 style='color:#fff;margin:0;'>MarxStein Group</h2></div><div style='background:#fff;padding:24px;border:1px solid #e8e8e8;border-radius:0 0 12px 12px;'><p>{'Cher(e)' if is_fr else 'Dear'} {d.name},</p><p>{'Merci pour votre réservation. Nous vous contacterons sous peu.' if is_fr else 'Thank you for your booking. We will contact you shortly.'}</p><p><strong>{d.vehicle}</strong> — {d.days} {'jours' if is_fr else 'days'} — {d.total}</p><p style='margin-top:20px;font-size:13px;color:#888;'>MarxStein Group — Douala, Cameroon<br>WhatsApp: +237 651 536 837</p></div></div>")
    except: pass
    return {"success": True}

@app.get("/api/bookings")
async def get_bookings(email: str):
    db = get_db()
    rows = db.execute("SELECT id,vehicle,pickup,days,service,total,status,created_at FROM bookings WHERE user_email=? ORDER BY id DESC", (email,)).fetchall()
    db.close()
    return {"bookings": [dict(r) for r in rows]}

# ─── Contact ───
@app.post("/api/contact")
async def contact(d: ContactReq):
    now = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    html = f"<div style='font-family:Arial;max-width:600px;'><div style='background:#4B2D7F;padding:20px;border-radius:12px 12px 0 0;'><h2 style='color:#fff;margin:0;'>New Inquiry</h2><p style='color:rgba(255,255,255,.8);font-size:14px;'>{now}</p></div><div style='background:#fff;padding:24px;border:1px solid #e8e8e8;border-radius:0 0 12px 12px;'><p><strong>{d.name}</strong> ({d.email})</p>{'<p>Phone: '+d.phone+'</p>' if d.phone else ''}{'<p>Subject: '+d.subject+'</p>' if d.subject else ''}<p style='white-space:pre-wrap;'>{d.message}</p></div></div>"
    try: send_email(COMPANY_EMAIL, f"Inquiry from {d.name}", html, reply_to=d.email)
    except: pass
    return {"success": True}

# ─── Admin ───
@app.get("/api/admin/data")
async def admin_data(email: str, password: str):
    db = get_db()
    h = hashlib.sha256(password.encode()).hexdigest()
    admin = db.execute("SELECT id FROM users WHERE email=? AND password_hash=? AND role='admin'", (email, h)).fetchone()
    if not admin:
        db.close()
        return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    users = [dict(r) for r in db.execute("SELECT id,name,email,phone,role,created_at FROM users ORDER BY id DESC").fetchall()]
    bookings = [dict(r) for r in db.execute("SELECT id,name,email,vehicle,pickup,days,total,status,created_at FROM bookings ORDER BY id DESC").fetchall()]
    db.close()
    return {"users": users, "bookings": bookings}

@app.get("/api/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
