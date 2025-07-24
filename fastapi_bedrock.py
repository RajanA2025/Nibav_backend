

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from db import setup_database, save_user_info, get_user_count, save_interaction, user_exists, create_connection
from db import update_user_with_tracking, get_user_update_history
from bedrock_search import initialize_bedrock_index, get_answer_bedrock, add_pdf_to_bedrock_index, generate_answer_with_bedrock
from bedrock_faiss_indexer import BedrockFAISSIndexer
from datetime import datetime, timedelta
import os
import glob
import shutil
import re
import PyPDF2
import pandas as pd
from pptx import Presentation
from docx import Document
import difflib
import logging
import camelot
from psycopg2 import errors
import boto3
import json
import re
import pandas as pd
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Literal
import traceback

app = FastAPI()

# Allow CORS for all origins (for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_database()

# In-memory session state (for demo; use a real session store in production)
session_state = {
    "admin_authenticated": False,
    "admin_password_attempts": 0,
    "admin_login_step": None,
    "admin_email_attempt": "",
    "admin_password_attempt": "",
    "show_admin_login": False,
    "bedrock_indexer": None,
    "role": None,
    "last_activity": None,  # Track last activity for session timeout
    "session_id": None,  # Add session ID for better tracking
}

# Add this at the top, after session_state definition
conversation_state = {}  # {email: {"last_question": ..., "last_answer": ..., "last_branch_results": ...}}

# Session timeout configuration
SESSION_TIMEOUT_MINUTES = 20  # 20 minutes

# --- Used Files Tracking ---
USED_FILES_PATH = os.path.join("data", "used_files.txt")

def normalize_filename(filename):
    return os.path.basename(filename).strip().lower()

def mark_file_used(filename):
    norm = normalize_filename(filename)
    logging.debug(f"[mark_file_used] Marking as used: {norm}")
    if not os.path.exists(USED_FILES_PATH):
        with open(USED_FILES_PATH, "w") as f:
            f.write(f"{norm}\n")
        logging.debug(f"[mark_file_used] used_files.txt created and {norm} written.")
        return
    with open(USED_FILES_PATH, "r+") as f:
        used = set(normalize_filename(line) for line in f if line.strip())
        if norm not in used:
            f.write(f"{norm}\n")
            logging.debug(f"[mark_file_used] {norm} appended to used_files.txt.")
        else:
            logging.debug(f"[mark_file_used] {norm} already present in used_files.txt.")

def is_file_used(filename):
    norm = normalize_filename(filename)
    if not os.path.exists(USED_FILES_PATH):
        logging.debug(f"[is_file_used] used_files.txt does not exist. Returning False for {norm}.")
        return False
    with open(USED_FILES_PATH, "r") as f:
        used = set(normalize_filename(line) for line in f if line.strip())
        result = norm in used
        logging.debug(f"[is_file_used] {norm} in used_files.txt? {result}")
        return result

def list_data_files():
    data_dir = "data"
    files = []
    if os.path.exists(data_dir):
        files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f)) and f.lower().endswith((".csv", ".pdf"))]
    logging.debug(f"[list_data_files] Files found: {files}")
    return files


def trim_by_chars(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    else:
        return text[:limit].rsplit(' ', 1)[0] + '...'

def extract_main_word(filename):
    return os.path.splitext(filename)[0].replace("_", " ").capitalize()

def save_interaction(email, user_query, bot_response):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO chat_history (email, user_query, bot_response, timestamp)
        VALUES (%s, %s, %s, NOW())
        """,
        (email, user_query, bot_response)
    )
    conn.commit()
    conn.close()



def extract_main_word(filename):
    name = os.path.splitext(filename)[0]
    main_word = name.split('_')[0].split(' ')[0]
    return main_word.capitalize()

def trim_to_tokens(text, max_tokens=100):
    tokens = re.findall(r'\b\w+\b', text)
    if len(tokens) <= max_tokens:
        return text
    count = 0
    for match in re.finditer(r'\b\w+\b', text):
        count += 1
        if count == max_tokens:
            end_pos = match.end()
            return text[:end_pos] + '...'
    return text

def is_list_like(text):
    if '\n' in text:
        return True
    if re.search(r'\d+\.', text):
        return True
    if ';' in text:
        return True
    return False

def format_points(text, max_tokens=100):
    points = re.split(r'\n|;|\d+\.', text)
    points = [p.strip() for p in points if p.strip()]
    result = []
    used_tokens = 0
    for p in points:
        p_trimmed = trim_to_tokens(p, max_tokens - used_tokens)
        p_tokens = len(re.findall(r'\b\w+\b', p_trimmed))
        if used_tokens + p_tokens > max_tokens:
            break
        result.append(f'- {p_trimmed}')
        used_tokens += p_tokens
        if used_tokens >= max_tokens:
            break
    return '\n'.join(result)

# Helper: Reprocess all files in data folder and reload index
def reprocess_and_reload_index():
    data_dir = "data"
    index_path = "bedrock_faiss_index"
    indexer = BedrockFAISSIndexer(index_path=index_path)
    files = os.listdir(data_dir)
    used_files = set()
    for file in files:
        file_path = os.path.join(data_dir, file)
        cache_path = file_path + ".embeddings.pkl"
        if file.lower().endswith(".csv"):
            if os.path.getsize(file_path) == 0:
                logging.warning(f"Skipping empty CSV file: {file}")
                continue
            try:
                indexer.process_csv(file_path)
                mark_file_used(file)
                used_files.add(normalize_filename(file))
            except Exception as e:
                logging.error(f"Error processing {file}: {e}")
        elif file.lower().endswith(".pdf"):
            try:
                indexer.process_pdf(file_path)
                mark_file_used(file)
                used_files.add(normalize_filename(file))
            except Exception as e:
                logging.error(f"Error processing {file}: {e}")
    # Rewrite used_files.txt to only include files that still exist
    with open(USED_FILES_PATH, "w") as f:
        for fname in used_files:
            f.write(f"{fname}\n")
    indexer.save_index(index_path)
    return initialize_bedrock_index()

def is_privileged_authenticated():
    if not session_state.get("admin_authenticated"):
        return False
    if session_state.get("role", "").lower() not in ["admin", "sales"]:  # Fixed: use lowercase
        return False
    
    last = session_state.get("last_activity")
    if not last:
        # No last activity recorded, session is invalid
        session_state["admin_authenticated"] = False
        return False
    
    # Check if session has expired
    if (datetime.now() - last > timedelta(minutes=SESSION_TIMEOUT_MINUTES)):
        # Session expired
        session_state["admin_authenticated"] = False
        session_state["role"] = None
        session_state["last_activity"] = None
        session_state["session_id"] = None
        return False
    
    # Session is valid, update last activity (but not on every call to reduce overhead)
    # Only update if more than 5 minutes have passed since last update
    if (datetime.now() - last > timedelta(minutes=20)):
        session_state["last_activity"] = datetime.now()
    
    return True

# --- Admin Endpoints ---
@app.post("/admin/login")
def admin_login(email: str, password: str):
    # Query the sales_persons_data table for this email and password
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, name FROM sales_persons_data WHERE email = %s AND password = %s",
        (email, password)
    )
    result = cursor.fetchone()
    conn.close()

    if not result:
        # No such user or wrong password
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role, name = result
    session_state["admin_authenticated"] = True
    session_state["role"] = role
    session_state["name"] = name  # Store the name
    session_state["email"] = email  # Store the admin's email
    session_state["last_activity"] = datetime.now()

    if role.lower() == "admin":
        return {"success": True, "message": "Admin authenticated!", "role": "admin"}
    elif role.lower() == "sales":
        return {"success": True, "message": "Sales person authenticated!", "role": "sales"}
    else:
        return {"success": True, "message": f"{role} authenticated!", "role": role}

@app.post("/admin/logout")
def admin_logout():
    session_state["admin_authenticated"] = False
    session_state["admin_password_attempts"] = 0
    session_state["admin_login_step"] = None
    session_state["admin_email_attempt"] = ""
    session_state["admin_password_attempt"] = ""
    session_state["show_admin_login"] = False
    session_state["last_activity"] = None
    session_state["role"] = None
    session_state["email"] = None  # Clear the email
    session_state["session_id"] = None
    return {"success": True, "message": "Logged out successfully."}

@app.get("/admin/files")
def get_files():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    files = list_data_files()
    # Add 'used' marker
    files_with_status = [
        {"filename": f, "used": is_file_used(f)} for f in files
    ]
    return {"files": files_with_status}


@app.post("/admin/upload")
def upload_file(file: UploadFile = File(...)):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":
        logging.error("Upload attempt by unauthorized user or non-admin.")
        raise HTTPException(status_code=403, detail="Only admin can upload files.")

    allowed_exts = ('.csv', '.pdf', '.ppt', '.pptx', '.doc', '.docx')
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    logging.info(f"[UPLOAD] Received file: {filename} (ext: {ext})")

    if ext not in allowed_exts:
        logging.error(f"[UPLOAD] File type not allowed: {ext}")
        raise HTTPException(status_code=400, detail="Only CSV, PDF, PPT, or Word files are allowed.")

    # Save file to data folder
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    file_path = os.path.join(data_dir, filename)
    file.file.seek(0)
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    logging.info(f"[UPLOAD] File saved to {file_path}")

    # Process file and update FAISS index
    try:
        indexer = BedrockFAISSIndexer(index_path="bedrock_faiss_index")
        if ext == ".csv":
            logging.info(f"[UPLOAD] Processing CSV: {file_path}")
            indexer.process_csv(file_path)
        elif ext == ".pdf":
            logging.info(f"[UPLOAD] Processing PDF: {file_path}")
            indexer.process_pdf(file_path)
        else:
            logging.error(f"[UPLOAD] Unsupported file type: {ext}")
            raise HTTPException(status_code=400, detail="Unsupported file type.")
        indexer.save_index()
        logging.info(f"[UPLOAD] Index saved. Marking file as used: {filename}")
        mark_file_used(filename)
        session_state["bedrock_indexer"] = None
        logging.info(f"[UPLOAD] Upload and processing complete for {filename}")
        return {"success": True, "message": f"File '{filename}' uploaded and processed successfully."}
    except Exception as e:
        logging.error(f"[UPLOAD] Error processing uploaded file {filename}: {repr(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {repr(e)}\n{traceback.format_exc()}")


@app.delete("/admin/delete/{filename}")
def delete_file(filename: str):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete files.")
    file_path = os.path.join("data", filename)
    cache_path = file_path + ".embeddings.pkl"
    if os.path.exists(file_path):
        os.remove(file_path)
        if os.path.exists(cache_path):
            os.remove(cache_path)
        # Rebuild index ONLY from current files
        reprocess_and_reload_index()
        # Clear in-memory cached index
        session_state["bedrock_indexer"] = None
        return {"success": True, "message": "File deleted and index reloaded successfully"}
    else:
        raise HTTPException(status_code=404, detail="File not found.")



@app.get("/chatusers/list")
def get_userschat_list():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            u.email,
            u.phone,
            latest.chat_date,
            latest.chat_time,
            u.status,
            u.description,
            u.summary,
            u.updated_by,
            u.updated_at
        FROM users u
        LEFT JOIN (
            SELECT DISTINCT ON (email) email, chat_date, chat_time
            FROM chat_history
            ORDER BY email, chat_date DESC, chat_time DESC
        ) latest ON u.email = latest.email
        ORDER BY latest.chat_date DESC NULLS LAST, latest.chat_time DESC NULLS LAST
    ''')
    
    users = cursor.fetchall()
    conn.close()

    return {
        "users": [
            {
                "email": u[0],
                "phone": u[1],
                "chat_date": datetime.strptime(str(u[2]), "%Y-%m-%d").strftime("%d/%m/%Y") if u[2] else None,
                "chat_time": datetime.strptime(str(u[3]), "%H:%M:%S.%f").strftime("%H:%M") if u[3] else None,
                "status": u[4],
                "description": u[5],
                   "summary":u[6],
                "updated_by": u[7],

                "updated_at": u[8].isoformat() if u[7] else None,
             
            } for u in users
        ]
    }



@app.get("/users/list")
def get_users_list():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    
    conn = create_connection()
    cursor = conn.cursor()

    # Get recent users with extracted date and time (not full timestamp)
    cursor.execute('''
        SELECT DISTINCT ON (u.email)
            u.email,
            
            c.password,
            c.role,
            c.name,
            c.created_at
        FROM sales_persons_data u
        JOIN sales_persons_data c ON u.email = c.email
        ORDER BY u.email, c.id DESC
        LIMIT 100
    ''')
    users = cursor.fetchall()
    conn.close()

    return {
        "users": [
            {
                "email": u[0],
    
                "password": u[1],
                "role": u[2],
                "name": u[3],
                "created_at": u[4]
            } for u in users
        ]
    }


@app.get("/users/history")
def get_user_history(email: str = Query(...)):
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_query, bot_response,chat_date,chat_time FROM chat_history
        WHERE email = %s
        ORDER BY id DESC
        LIMIT 100
    """, (email,))
    history = cursor.fetchall()
    conn.close()
    # Return as list of dicts
    return {"history": [{"user_query": h[0], "bot_response": h[1], "chat_date": h[2], "chat_time": h[3]} for h in history]}

# --- User Endpoints ---
@app.post("/user/register")
def user_register(
    email: str = Form(...),
    phone: str = Form(...),
    country: str = Form('India'),
    status: str = Form('pending')
    ):
    import re
    from email_validator import validate_email, EmailNotValidError

    # --- Phone Number Validation ---
    phone = phone.strip()
    if not re.fullmatch(r"\d{10}", phone):
        return {"success": False, "message": "Phone number must be exactly 10 digits (not more, not less)."}
    if phone[0] in ('8', '9'):
        return {"success": False, "message": "Phone number must be 10"}

    # --- Email Validation ---
    email = email.strip()
    if '@' not in email or '.' not in email:
        return {"success": False, "message": "Email must contain both '@' and '.' characters."}
    try:
        validate_email(email)
    except EmailNotValidError:
        return {"success": False, "message": "Invalid email address."}

    # --- User Existence Check and Save ---
    if not user_exists(email, phone):
        save_user_info(email, phone, country, status)
    return {"success": True, "message": "User registered."}

def extract_location_from_query(query: str) -> str:
    query_lower = query.lower()
    data_dir = "data"
    locations_found = set()

    # Search each CSV for a 'city' column and collect city names
    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join(data_dir, filename))
                if 'city' in df.columns:
                    for city in df['city'].dropna().unique():
                        city_lower = str(city).strip().lower()
                        if city_lower in query_lower:
                            locations_found.add(city_lower)
            except Exception:
                continue

    # Return the first matched location or empty string
    return list(locations_found)[0] if locations_found else ""

@app.post("/chat")
def chat(email: str = Form(...), user_query: str = Form(...)):
    import os
    import pandas as pd

    user_query_lower = user_query.lower().strip()

    # 1. Handle greetings and small talk
    greetings = {
        "hi": "Hi! How can I assist you today?",
        "hii": "Hi! How can I assist you today?",
        "hello": "Hello! How can I help you?",
        "hey": "Hey there! How can I help you?",
        "good morning": "Good morning! How can I assist you today?",
        "how are you": "I'm just a bot, but I'm here to help you! How can I assist you?",
        "whats your name": "I'm your enterprise assistant bot, here to help you with your queries!",
        "who are you": "I'm your enterprise assistant bot, here to help you with your queries!",
        "how you help me": "I can answer your questions from uploaded documents. How can I help you today?",
        "ok": "Ok, how can I help you today?",
        "okay": "Ok, how can I help you today?",
        "thanks": "You're welcome! How can I help you today?",
        "thank you": "You're welcome! Let me know if there's anything else I can assist you with.",
        "thank u": "You're welcome!",
        "thx": "You're welcome!",
        "ty": "You're welcome!"
    }
    normalized_query = user_query_lower
    if normalized_query in greetings:
        polite_reply = greetings[normalized_query]
        save_interaction(email, user_query, polite_reply)
        conversation_state[email] = {
            "last_question": user_query,
            "last_answer": polite_reply
        }
        return {
            "long_desc": polite_reply,
            "more_available": False
        }

    # 1.5. Nibav contact info detection (robust)
    NIBAV_CONTACT = "+91 78248 12121"
    NIBAV_EMAIL = "info@nibavlifts.com"
    contact_keywords = [
        "contact number", "phone number", "contact info", "contact details", "contact", "phone", "email",
        "how do i contact", "nibav contact", "nibav phone", "nibav email", "give me nibav contact", "give me nibav phone", "give me nibav email",
        "what is the contact number of the nibav lift", "nibav lifts contact", "give me contact number", "give me phone number", "main contact"
    ]
    # If the query is just 'contact number' or similar, or contains 'nibav' and 'contact' or 'phone' or 'email'
    if any(kw in user_query_lower for kw in contact_keywords) or (
        ("nibav" in user_query_lower) and ("contact" in user_query_lower or "phone" in user_query_lower or "email" in user_query_lower)
    ):
        reply = f"Nibav Lifts main contact:\nPhone: {NIBAV_CONTACT}\nEmail: {NIBAV_EMAIL}"
        save_interaction(email, user_query, reply)
        return {"long_desc": reply, "more_available": False}

    import os
    from difflib import get_close_matches

    # Map known localities to main city names
    locality_to_city = {
        "porur": "chennai",
        "adyar": "chennai",
        "jp nagar": "bangalore",
        "kirti nagar": "delhi",
        # Add more as needed
    }

    def is_branch_query(user_query):
        keywords = ["branch", "branches", "location", "office", "address", "phone", "email", "contact","details","branch details"]
        return any(word in user_query.lower() for word in keywords)

    def load_branches():
        path = os.path.join("data", "all_branches.csv")
        return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

    def find_branch_details(city_query):
        df = load_branches()
        if 'city' in df.columns:
            matches = df[df['city'].str.lower() == city_query.lower()]
            if not matches.empty:
                return matches.to_dict(orient='records')
        return None

    def get_main_contact():
        df = load_branches()
        if 'phone' in df.columns and 'email' in df.columns and not df.empty:
            phone = df.iloc[0]['phone']
            email = df.iloc[0]['email']
            return phone, email
        return None, None

    def build_csv_context():
        df = load_branches()
        if not df.empty:
            return "\n".join([
                f"{row['city']}, {row['state']}, {row['country']}: "
                f"{row['address']} | {row['phone']} | {row['email']}"
                for _, row in df.iterrows()
            ])
        return ""

    def find_best_city_match(word, cities):
        if word in cities:
            return word
        match = get_close_matches(word, cities, n=1, cutoff=0.8)
        return match[0] if match else None

    def handle_branch_query(user_query):
        df = load_branches()
        words = user_query.lower().split()
        possible_states = [s.lower() for s in df['state'].dropna().unique()] if not df.empty and 'state' in df.columns else []
        possible_countries = [c.lower() for c in df['country'].dropna().unique()] if not df.empty and 'country' in df.columns else []
        possible_cities = [c.lower() for c in df['city'].dropna().unique()] if not df.empty and 'city' in df.columns else []

        city = None
        state = None
        country = None
        for w in words:
            if w in possible_cities:
                city = w
                break
            if w in possible_states:
                state = w
            if w in possible_countries:
                country = w

        if city:
            details = find_branch_details(city)
            if details:
                b = details[0]
                return (
                    f"Branch details for {b['city']}, {b['state']} (Country: {b['country']}):\n"
                    f"Address: {b['address']}\nPhone: {b['phone']}\nEmail: {b['email']}"
                )
            else:
                return "Sorry, there is no branch in that place."
        elif state:
            state_matches = df[df['state'].str.lower() == state]
            if not state_matches.empty:
                reply = f"Branches in {state.title()}:\n"
                for _, b in state_matches.iterrows():
                    reply += (
                        f"- {b['city']}: {b['address']} | Phone: {b['phone']} | Email: {b['email']}\n"
                    )
                return reply.strip()
            else:
                return "Sorry, there is no branch in that place."
        elif country:
            country_matches = df[df['country'].str.lower() == country]
            if not country_matches.empty:
                reply = f"Branches in {country.title()}:\n"
                for _, b in country_matches.iterrows():
                    reply += (
                        f"- {b['city']}, {b['state']}: {b['address']} | Phone: {b['phone']} | Email: {b['email']}\n"
                    )
                return reply.strip()
            else:
                return "Sorry, there is no branch in that place."
        else:
            return "Sorry, there is no branch in that place."

    # --- The main handler inside your FastAPI route ---
    if is_branch_query(user_query):
        reply_from_csv = handle_branch_query(user_query)

        # Optionally: pass context to LLM
        csv_context = build_csv_context()
        try:
            llm_answer = generate_answer_with_bedrock(user_query, csv_context)
        except:
            llm_answer = None

        # Prefer CSV-based answer if valid
        if reply_from_csv and not reply_from_csv.lower().startswith("sorry, there is no branch"):
            reply = reply_from_csv
        else:
            reply = "Sorry, there is no branch in that place."

        save_interaction(email, user_query, reply)
        conversation_state[email] = {"last_question": user_query, "last_answer": reply}
        update_summary_if_needed(email)

        return {"long_desc": reply, "more_available": False}



    # 4. Check if any files exist in the knowledge base
    data_dir = "data"
    all_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    if not all_files:
        msg = "No files available. Please upload documents for me to assist you."
        save_interaction(email, user_query, msg)
        conversation_state[email] = {
            "last_question": user_query,
            "last_answer": msg
        }
        update_summary_if_needed(email)
        return {"short_desc": msg, "long_desc": None, "more_available": False}

    # 5. Search the knowledge base (PDF + CSV, via FAISS index)
    bedrock_indexer = initialize_bedrock_index()
    results = bedrock_indexer.search(user_query, k=3, threshold=0.15)

    if results:
        # Gather top-k context
        context_chunks = []
        for doc, _ in results:
            if doc.get('text'):
                context_chunks.append(doc.get('text'))
            elif doc.get('answer'):
                context_chunks.append(doc.get('answer'))
            elif doc.get('details'):
                context_chunks.append(doc.get('details'))
        context = "\n\n".join(context_chunks)

        # Prefer concise answer if top result is from CSV
        best_doc, best_score = results[0]
        short_ans = ""
        if best_doc.get('source') == 'csv':
            short_ans = best_doc.get('answer') or best_doc.get('text') or ""

        # --- New: Check if context is relevant before calling LLM ---
        # Use simple keyword check: at least one keyword from user_query must be in context
        keywords = [w for w in user_query.lower().split() if len(w) > 2]
        context_for_check = context.lower()
        if not any(k in context_for_check for k in keywords):
            msg = "Sorry, I do not have information on that."
            save_interaction(email, user_query, msg)
            conversation_state[email] = {
                "last_question": user_query,
                "last_answer": msg
            }
            update_summary_if_needed(email)
            return {"long_desc": msg, "more_available": False}

        # Always use LLM to generate the final answer
        try:
            llm_answer = generate_answer_with_bedrock(user_query, context)
        except Exception as e:
            llm_answer = None

        # Post-process: trim to first 2 sentences, remove repeats
        def trim_to_sentences(text, num_sentences=2):
            sentences = re.split(r'(?<=[.!?])\s+', text.strip())
            seen = set()
            result = []
            for s in sentences:
                s_clean = s.strip()
                if s_clean and s_clean.lower() not in seen:
                    result.append(s_clean)
                    seen.add(s_clean.lower())
                if len(result) >= num_sentences:
                    break
            return ' '.join(result)

        if llm_answer:
            trimmed_llm = trim_to_sentences(llm_answer, 2)
            reply = trimmed_llm
        elif short_ans:
            reply = trim_to_sentences(short_ans, 2)
        else:
            reply = trim_to_sentences(context, 2)

        save_interaction(email, user_query, reply)
        conversation_state[email] = {
            "last_question": user_query,
            "last_answer": reply
        }
        update_summary_if_needed(email)
        return {"long_desc": reply, "more_available": False}
    else:
        msg = "Sorry, I do not have information on that."
        save_interaction(email, user_query, msg)
        conversation_state[email] = {
            "last_question": user_query,
            "last_answer": msg
        }
        update_summary_if_needed(email)
        return {"long_desc": msg, "more_available": False}





def update_summary_if_needed(email):
    # Fetch last 3 questions
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_query FROM chat_history WHERE email = %s ORDER BY id DESC LIMIT 3", (email,))
    last_questions = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not last_questions or len(last_questions) < 3:
        # Not enough questions to summarize
        return

    # Combine last 3 questions into a single text blob (chronological order)
    chat_text = " ".join(reversed(last_questions)).lower()

    # Rule-based tagging
    if any(word in chat_text for word in ["price", "cost", "buy", "purchase", "quotation", "quote"]):
        summary = "User appears to be interested in purchasing a lift."
    elif any(word in chat_text for word in ["problem", "issue", "repair", "not working", "support"]):
        summary = "User is mostly making support-related queries."
    elif any(word in chat_text for word in ["branch", "location", "city", "state", "office"]):
        summary = "User is enquiring about branches and locations."
    else:
        summary = "User is asking general questions."

    # Update the summary column in users table
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET summary = %s WHERE email = %s", (summary, email))
    conn.commit()
    conn.close()



@app.get("/user/count")
def user_count():
    return {"count": get_user_count()} 




# New API: Chat analytics (total chats per day, week, month)
@app.get("/analytics/chat_counts")
def chat_counts():
    try:
        conn = create_connection()
        cursor = conn.cursor()

        # Total chats per day
        cursor.execute("""
            SELECT chat_date, COUNT(*) as total_chats
            FROM chat_history
            GROUP BY chat_date
            ORDER BY chat_date DESC
            LIMIT 30
        """)
        daily = cursor.fetchall()

        # Last 7 days aggregation (rolling week)
        today = datetime.now().date()
        seven_days_ago = today - timedelta(days=6)
        
        # Get chats for each day in the last 7 days
        cursor.execute("""
            SELECT chat_date, COUNT(*) as total_chats
            FROM chat_history
            WHERE chat_date >= %s AND chat_date <= %s
            GROUP BY chat_date
            ORDER BY chat_date DESC
        """, (seven_days_ago, today))
        
        daily_chats = cursor.fetchall()
        
        # Create a complete 7-day list with 0 for days with no chats
        total_chats_7_days = 0
        for i in range(7):
            current_date = today - timedelta(days=i)
            current_date_str = current_date.strftime('%Y-%m-%d')
            # Find if this date has chat data
            chat_count = 0
            for row in daily_chats:
                if str(row[0]) == current_date_str:
                    chat_count = row[1]
                    break
            total_chats_7_days += chat_count
        # Format date range as dd/mm/yyyy-dd/mm/yyyy
        date_range = f"{seven_days_ago.strftime('%d/%m/%Y')}-{today.strftime('%d/%m/%Y')}"
        weekly = {
            "date_range": date_range,
            "total_chats": total_chats_7_days
        }

        # Monthly aggregation
        try:
            cursor.execute("""
                SELECT DATE_TRUNC('month', chat_date) as month_start, COUNT(*) as total_chats
                FROM chat_history
                GROUP BY month_start
                ORDER BY month_start DESC
                LIMIT 12
            """)
            monthly_raw = cursor.fetchall()
            monthly = []
            for row in monthly_raw:
                month_start = row[0]
                if isinstance(month_start, str):
                    month_start_dt = datetime.strptime(month_start, "%Y-%m-%d")
                else:
                    month_start_dt = month_start
                # Calculate last day of the month
                if month_start_dt.month == 12:
                    next_month = month_start_dt.replace(year=month_start_dt.year+1, month=1, day=1)
                else:
                    next_month = month_start_dt.replace(month=month_start_dt.month+1, day=1)
                month_end_dt = next_month - timedelta(days=1)
                month_range = f"{month_start_dt.strftime('%d-%m-%Y')} -- {month_end_dt.strftime('%d-%m-%Y')}"
                monthly.append({"month_range": month_range, "total_chats": row[1]})
        except Exception:
            # Fallback for SQLite
            cursor.execute("""
                SELECT strftime('%Y-%m', chat_date) as month_start, COUNT(*) as total_chats
                FROM chat_history
                GROUP BY month_start
                ORDER BY month_start DESC
                LIMIT 12
            """)
            monthly_raw = cursor.fetchall()
            monthly = []
            for row in monthly_raw:
                year, month = row[0].split('-')
                month_start_dt = datetime.strptime(f'{year}-{month}-01', "%Y-%m-%d")
                if int(month) == 12:
                    next_month = month_start_dt.replace(year=month_start_dt.year+1, month=1, day=1)
                else:
                    next_month = month_start_dt.replace(month=month_start_dt.month+1, day=1)
                month_end_dt = next_month - timedelta(days=1)
                month_range = f"{month_start_dt.strftime('%d-%m-%Y')} -- {month_end_dt.strftime('%d-%m-%Y')}"
                monthly.append({"month_range": month_range, "total_chats": row[1]})

        conn.close()

        return {
            "daily": [{"date": str(row[0]), "total_chats": row[1]} for row in daily],
            "weekly": weekly,
            "monthly": monthly,
        }
    except Exception as e:
        print("Analytics error:", e)
        return {"error": str(e)} 
@app.post("/user/create")
def create_sales_person(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str= Form(...) 
 

):
    # if not is_privileged_authenticated() or session_state.get("role", "").lower() not in ["admin", "sales"]:
    #     raise HTTPException(status_code=403, detail="Only admin or sales can create sales persons.")
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can upload files.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO sales_persons_data (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (name, email, password, role)
        )
        conn.commit()
        return {"success": True, "message": f"Admin person '{email}' created successfully."}
    except Exception as e:
        conn.rollback()
        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
            return {"success": False, "message": "Email already exists. Please use a different email."}
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close()
@app.put("/user/update")
def update_sales_person(
    name: str = Form(None),
    email: str = Form(...),
    password: str = Form(None),
    role: str = Form(None)
):
    # if not is_privileged_authenticated() or session_state.get("role", "").lower() not in ["admin", "sales"]:
    #     raise HTTPException(status_code=403, detail="Only admin or sales can update sales persons.")
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can create the persons.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Build dynamic update query
        fields = []
        values = []
        if name is not None:
            fields.append("name = %s")
            values.append(name)
        if password is not None:
            fields.append("password = %s")
            values.append(password)
        if role is not None:
            fields.append("role = %s")
            values.append(role)
        if not fields:
            return {"success": False, "message": "No fields to update."}
        values.append(email)
        query = f"UPDATE sales_persons_data SET {', '.join(fields)} WHERE email = %s"
        cursor.execute(query, tuple(values))
        if cursor.rowcount == 0:
            return {"success": False, "message": f"No sales person found with email '{email}'."}
        conn.commit()
        return {"success": True, "message": f"Admin person '{email}' updated successfully."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close()

@app.delete("/user/delete")
def delete_sales_person(email: str = Form(...)):
    # if not is_privileged_authenticated() or session_state.get("role", "").lower() not in ["admin", "sales"]:
    #     raise HTTPException(status_code=403, detail="Only admin or sales can delete sales persons.")
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can upload files.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM sales_persons_data WHERE email = %s",
            (email,)
        )
        if cursor.rowcount == 0:
            return {"success": False, "message": f"No sales person found with email '{email}'."}
        conn.commit()
        return {"success": True, "message": f"{user_role} person '{email}' deleted successfully."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close() 
@app.get("/admin/top-questions")
def get_top_questions():
    if not is_privileged_authenticated():  # Allow both admin and sales to view
        raise HTTPException(status_code=401, detail="Not authenticated.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT user_query, COUNT(*) as count
            FROM chat_history
            GROUP BY user_query
            ORDER BY count DESC
            LIMIT 15
        """)
        results = cursor.fetchall()
        return {
            "top_questions": [
                {"question": row[0], "count": row[1]}
                for row in results
            ]
        }
    finally:
        conn.close()

@app.get("/admin/session-status")
def get_session_status():
    """Check current session status for debugging"""
    if not session_state.get("admin_authenticated"):
        return {
            "authenticated": False,
            "message": "Not authenticated",
            "last_activity": None,
            "session_id": None
        }
    
    last_activity = session_state.get("last_activity")
    if last_activity:
        time_remaining = SESSION_TIMEOUT_MINUTES - ((datetime.now() - last_activity).total_seconds() / 60)
        return {
            "authenticated": True,
            "role": session_state.get("role"),
            "email": session_state.get("email"),  # Include email in session status
            "session_id": session_state.get("session_id"),
            "last_activity": last_activity.isoformat(),
            "time_remaining_minutes": round(max(0, time_remaining), 1),
            "session_timeout_minutes": SESSION_TIMEOUT_MINUTES
        }
    else:
        return {
            "authenticated": False,
            "message": "Session has no last activity",
            "last_activity": None,
            "session_id": None
        }
@app.post("/admin/estimate-memory")
def estimate_pdf_memory(file: UploadFile = File(...)):
    """Estimate memory usage for processing a PDF file"""
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can estimate memory usage.")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for memory estimation.")

    try:
        # Save file temporarily
        temp_path = f"temp_{file.filename}"
        file.file.seek(0)
        with open(temp_path, "wb") as f:
            f.write(file.file.read())
        
        # Estimate memory usage
        indexer = BedrockFAISSIndexer(index_path="bedrock_faiss_index")
        estimate = indexer.estimate_memory_usage(temp_path)
        
        # Clean up temp file
        os.remove(temp_path)
        
        return estimate
    except Exception as e:
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error estimating memory: {str(e)}")


@app.put("/Chatuser/update")
def update_user_and_get_history(
    email: str = Form(...),
    status: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    # Extract user identity from session
    name = session_state.get("name", "unknown")
    role = session_state.get("role", "unknown").lower()
    updated_by = f"{role} ({name})"

    # Authorization check (only allow admin or sales to update)
    if not is_privileged_authenticated() or role not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin or sales can update user status and description.")
    
    # Perform update and track
    from db import update_user_with_tracking, get_user_update_history
    update_result = update_user_with_tracking(
        email=email,
        status=status,
        description=description,
        updated_by_email=updated_by
    )

    # Get update history
    update_history = get_user_update_history(email)

    # Response
    return {
        "success": True,
        "message": "User updated successfully",
        "updated_by": updated_by,
        "email": email,
        "update_result": update_result,
        "update_history": update_history
    }

def generate_summary_internal(email):
    # Step 1: Fetch user's chat history
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_query FROM chat_history WHERE email = %s", (email,))
    chat_rows = cursor.fetchall()
    conn.close()

    if not chat_rows:
        return None

    # Step 2: Combine chat queries into a single text blob
    chat_text = " ".join([row[0] for row in chat_rows]).lower()

    # Step 3: Simple rule-based tagging (can replace with LLM later)
    if any(word in chat_text for word in ["price", "cost", "buy", "purchase", "quotation", "quote"]):
        summary = "User appears to be interested in purchasing a lift."
    elif any(word in chat_text for word in ["problem", "issue", "repair", "not working", "support"]):
        summary = "User is mostly making support-related queries."
    elif any(word in chat_text for word in ["branch", "location", "city", "state", "office"]):
        summary = "User is enquiring about branches and locations."
    else:
        summary = "User is asking general questions."

    # Step 4: Update the users table
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET summary = %s WHERE email = %s", (summary, email))
    conn.commit()
    conn.close()

    return {"email": email, "summary": summary}
