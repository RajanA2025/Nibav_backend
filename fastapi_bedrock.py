from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from db import setup_database, save_user_info, get_user_count, save_interaction, user_exists, create_connection
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

# Session timeout configuration
SESSION_TIMEOUT_MINUTES = 20  # 20 minutes

def list_data_files():
    data_dir = "data"
    files = []
    if os.path.exists(data_dir):
        files = [f for f in os.listdir(data_dir) if f.lower().endswith((".csv", ".pdf"))]
    return files


def trim_by_chars(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    else:
        return text[:limit].rsplit(' ', 1)[0] + '...'

def extract_main_word(filename):
    return os.path.splitext(filename)[0].replace("_", " ").capitalize()

def list_data_files():
    data_dir = "data"
    return [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]

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
    indexer = BedrockFAISSIndexer()
    files = os.listdir(data_dir)
    for file in files:
        file_path = os.path.join(data_dir, file)
        if file.lower().endswith(".csv"):
            indexer.process_csv(file_path)
        elif file.lower().endswith(".pdf"):
            indexer.process_pdf(file_path)
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
        "SELECT role FROM sales_persons_data WHERE email = %s AND password = %s",
        (email, password)
    )
    result = cursor.fetchone()
    conn.close()

    if not result:
        # No such user or wrong password
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = result[0]
    session_state["admin_authenticated"] = True
    session_state["role"] = role
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
    session_state["session_id"] = None
    return {"success": True, "message": "Logged out successfully."}

@app.get("/admin/files")
def get_files():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"files": list_data_files()}


@app.post("/admin/upload")
def upload_file(file: UploadFile = File(...)):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can upload files.")

    allowed_exts = ('.csv', '.pdf', '.ppt', '.pptx', '.doc', '.docx')
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Only CSV, PDF, PPT, or Word files are allowed.")

    # Check file size and provide warnings for large files
    file.file.seek(0)
    file_content = file.file.read()
    file_size = len(file_content)
    file_size_mb = file_size / (1024 * 1024)
    
    # Reset file pointer for saving
    file.file.seek(0)

    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]

    if len(files) >= 20:

        raise HTTPException(status_code=400, detail="File upload limit reached. Please delete some files before uploading new ones.")

    # Save all files as-is without any conversion
    file_path = os.path.join(data_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Provide appropriate message based on file size
    if file_size_mb > 100:
        message = f"File uploaded successfully! ⚠️ Large file detected ({file_size_mb:.1f}MB). Processing may take several hours and consume significant AWS credits. Please be patient."
    elif file_size_mb > 50:
        message = f"File uploaded successfully! 📊 Medium file detected ({file_size_mb:.1f}MB). Processing may take 30-60 minutes."
    elif file_size_mb > 10:
        message = f"File uploaded successfully! 📄 File size: {file_size_mb:.1f}MB. Processing may take 10-30 minutes."
    else:
        message = f"File uploaded successfully! ✅ Small file ({file_size_mb:.1f}MB). Processing should be quick."
    
    reprocess_and_reload_index()
    session_state["bedrock_indexer"] = None
    return {"success": True, "message": message}


@app.delete("/admin/delete/{filename}")
def delete_file(filename: str):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can delete files.")

    file_path = os.path.join("data", filename)
    if os.path.exists(file_path):
        os.remove(file_path)

        # Rebuild index ONLY from current files
        reprocess_and_reload_index()

        # Clear in-memory cached index
        session_state["bedrock_indexer"] = None

        return {"success": True, "message": "File deleted and index reloaded successfully"}
    else:
        raise HTTPException(status_code=404, detail="File not found.")



@app.get("/chatusers/list")
def get_users_list():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    
    conn = create_connection()
    cursor = conn.cursor()

    # Get recent users with extracted date and time (not full timestamp)
    cursor.execute('''
        SELECT DISTINCT ON (u.email)
            u.email,
            u.phone,
            c.chat_date,
            c.chat_time,
            u.status,
            u.description
          
        FROM users u
        JOIN chat_history c ON u.email = c.email
        ORDER BY u.email DESC ,c.chat_date DESC,c.chat_time DESC
        LIMIT 100
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
               # "chat_date": u[2],
               # "chat_time": u[3],
                "status": u[4],
                "description": u[5]
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
def user_register(email: str = Form(...), phone: str = Form(...)):
    if not user_exists(email, phone):
        save_user_info(email, phone, "N/A")
    return {"success": True, "message": "User registered."}

# @app.post("/chat")
# def chat(email: str = Form(...), user_query: str = Form(...)):
    import os

    # 1. Handle greetings and small talk
    greetings = {
        "hi": "Hi! How can I assist you today?",
        "Hi there": "Hi! How can I assist you today?",
        "hello": "Hello! How can I help you?",
        "hey": "Hey there! How can I help you?",
        "good morning": "Good morning! How can I assist you today?",
        "how are you": "I'm just a bot, but I'm here to help you! How can I assist you?",
        "who are you": "I'm your assistant bot, here to help you with your queries!",
        "how you help me": "I can answer your questions from uploaded documents. How can I help you today?"
    }

    normalized_query = user_query.strip().lower()
    if normalized_query in greetings:
        polite_reply = greetings[normalized_query]
        save_interaction(email, user_query, polite_reply)
        return {
            "short_desc": polite_reply,
            "long_desc": None,
            "more_available": False
        }

    # 2. Check if any files exist in the data folder
    data_dir = "data"
    all_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    if not all_files:
        msg = "No files uploaded yet. Please upload documents so I can assist you."
        save_interaction(email, user_query, msg)
        return {
            "short_desc": msg,
            "long_desc": None,
            "more_available": False
        }

    # 3. Rebuild bedrock indexer from current files
    bedrock_indexer = initialize_bedrock_index()
    results = bedrock_indexer.search(user_query, k=3, threshold=0.15)

    if results:
        best_doc, _ = results[0]
        short_ans = best_doc.get('answer') or best_doc.get('text') or ""
        long_ans = best_doc.get('details') or best_doc.get('text') or ""

        # Trim short and long answer
        trimmed_short = format_points(short_ans, 60) if is_list_like(short_ans) else trim_to_tokens(short_ans, 60)
        trimmed_long = trim_to_tokens(long_ans, 200)

        # If long is too similar or empty, regenerate it
        if not trimmed_long or trimmed_long.lower() == trimmed_short.lower():
            context = "\n\n".join([
                doc.get('details') or doc.get('answer') or doc.get('text') or ""
                for doc, _ in results
            ]) or trimmed_short
            try:
                generated_long = generate_answer_with_bedrock(user_query, context)
                trimmed_long = trim_to_tokens(generated_long, 300)
            except:
                trimmed_long = None

        save_interaction(email, user_query, trimmed_short)

        return {
            "short_desc": trimmed_short,
            "long_desc": trimmed_long,
            "more_available": bool(trimmed_long)
        }

    else:
        topics_str = ", ".join([extract_main_word(f) for f in all_files])
        msg = f"Sorry, I couldn't find an answer to that. I have data only on: {topics_str}"
        save_interaction(email, user_query, msg)
        return {
            "short_desc": msg,
            "long_desc": msg,
            "more_available": False
        }


@app.post("/chat")
def chat(email: str = Form(...), user_query: str = Form(...)):
    import os

    greetings = {
        "hi": "Hi! How can I assist you today?",
        "hello": "Hello! How can I help you?",
        "hey": "Hey there! How can I help you?",
        "good morning": "Good morning! How can I assist you today?",
        "how are you": "I'm just a bot, but I'm here to help you! How can I assist you?",
        "who are you": "I'm your assistant bot, here to help you with your queries!",
        "how you help me": "I can answer your questions from uploaded documents. How can I help you today?"
    }

    normalized_query = user_query.strip().lower()
    if normalized_query in greetings:
        polite_reply = greetings[normalized_query]
        save_interaction(email, user_query, polite_reply)
        return {
            #"short_desc": polite_reply,
            "long_desc": polite_reply,
            "more_available": False 
        }

    # Check if files exist
    data_dir = "data"
    all_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    if not all_files:
        msg = "No files available. Please upload documents for me to assist you."
        save_interaction(email, user_query, msg)
        return {
            "short_desc": msg,
            "long_desc": None,
            "more_available": False
        }

    # Always reinitialize index based on current data
    bedrock_indexer = initialize_bedrock_index()
    results = bedrock_indexer.search(user_query, k=3, threshold=0.15)

    if results:
        best_doc, _ = results[0]
        short_ans = best_doc.get('answer') or best_doc.get('text') or ""
        long_ans = best_doc.get('details') or best_doc.get('text') or ""

        trimmed_short = format_points(short_ans, 60) if is_list_like(short_ans) else trim_to_tokens(short_ans, 60)
        trimmed_long = trim_to_tokens(long_ans, 200)


        if results:

            best_doc, _ = results[0]
            if best_doc.get('source') == 'csv':
                # --- CSV logic (keep as is) ---
                short_ans = best_doc.get('answer') or best_doc.get('text') or ""
                long_ans = best_doc.get('details') or best_doc.get('text') or ""
                trimmed_short = format_points(short_ans, 60) if is_list_like(short_ans) else trim_to_tokens(short_ans, 60)
                trimmed_long = trim_to_tokens(long_ans, 200)
                if not trimmed_long or trimmed_long.lower() == trimmed_short.lower():
                    context = "\n\n".join([
                        doc.get('details') or doc.get('answer') or doc.get('text') or ""
                        for doc, _ in results
                    ]) or trimmed_short
                    try:
                        generated_long = generate_answer_with_bedrock(user_query, context)
                        trimmed_long = trim_to_tokens(generated_long, 300)
                    except:
                        trimmed_long = None
                save_interaction(email, user_query, trimmed_short)
                return {
                    #"short_desc": trimmed_short,
                    "long_desc": trimmed_short+trimmed_long,

                    "more_available": bool(trimmed_long)
                }
            else:
                # --- PDF logic (improved) ---
                seen = set()
                context_chunks = []
                for doc, _ in results:
                    txt = doc.get('text', '')
                    if txt not in seen and len(context_chunks) < 3:
                        context_chunks.append(txt)
                        seen.add(txt)
                context = "\n\n".join(context_chunks)
                short_ans = context_chunks[0] if context_chunks else ""
                trimmed_short = format_points(short_ans, 60) if is_list_like(short_ans) else trim_to_tokens(short_ans, 60)
                trimmed_long = trim_to_tokens(context, 200)
                if not trimmed_long or trimmed_long.lower() == trimmed_short.lower():
                    try:
                        generated_long = generate_answer_with_bedrock(user_query, context)
                        trimmed_long = trim_to_tokens(generated_long, 300)
                    except:
                        trimmed_long = None
                save_interaction(email, user_query, trimmed_short)
                return {
                    #"short_desc":None,
                    "long_desc": trimmed_long,
                    "more_available": bool(trimmed_long)
                }

    else:
        topics_str = ", ".join([extract_main_word(f) for f in all_files])
        msg = f"Sorry, I couldn't find an answer to that."# I have data only on: {topics_str}"
        save_interaction(email, user_query, msg)
        return {
            #"short_desc": None,
            "long_desc": msg,
            "more_available": False
        }

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
    role: str = Form(...)
):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admin can create sales persons.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO sales_persons_data (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (name, email, password, role)
        )
        conn.commit()
        return {"success": True, "message": f"Sales person '{email}' created successfully."}
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
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update sales persons.")
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
        return {"success": True, "message": f"Sales person '{email}' updated successfully."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close()

@app.delete("/user/delete")
def delete_sales_person(email: str = Form(...)):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete sales persons.")
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
        return {"success": True, "message": f"Sales person '{email}' deleted successfully."}
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
        indexer = BedrockFAISSIndexer()
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
def update_users(
    # name: str = Form(None),
    email: str = Form(...),
    status: str = Form(None),
    description: str = Form(None)
):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin or sales can update user status and description.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Build dynamic update query
        fields = []
        values = []
        if status is not None:
            fields.append("status = %s")
            values.append(status)
        if description is not None:
            fields.append("description = %s")
            values.append(description)
        # if role is not None:
        #     fields.append("role = %s")
        #     values.append(role)
        if not fields:
            return {"failed": False, "message": "need to update status or description"}
        values.append(email)
        query = f"UPDATE users SET {', '.join(fields)} WHERE LOWER(email) = LOWER(%s)"
        cursor.execute(query, tuple(values))
        if cursor.rowcount == 0:
            return {"success": False, "message": f"No chat user found with email '{email}'."}
        conn.commit()
        return {"success": True, "message": f"chat user '{email}' updated successfully."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close()