import psycopg2

# PostgreSQL connection config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Vasala@#66118'
}

def create_connection():
    return psycopg2.connect(**DB_CONFIG)

def setup_database():
    conn = create_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(100),
            phone VARCHAR(15),
            country VARCHAR(100),
            status VARCHAR(50) DEFAULT 'pending',
            summary TEXT,
            updated_by VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add updated_by column if it doesn't exist (for existing databases)
    try:
        cursor.execute('''
            ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_by VARCHAR(100)
        ''')
    except:
        pass  # Column might already exist

    # Add updated_at column if it doesn't exist (for existing databases)
    try:
        cursor.execute('''
            ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ''')
    except:
        pass  # Column might already exist

    # Create chat_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            email VARCHAR(100),
            user_query TEXT,
            bot_response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create sales_persons_data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_persons_data (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            password VARCHAR(255),
            role VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create live_agent_requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_agent_requests (
            id SERIAL PRIMARY KEY,
            user_email VARCHAR(100),
            user_phone VARCHAR(15),
            request_reason TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            assigned_agent_email VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create live_agent_sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_agent_sessions (
            id SERIAL PRIMARY KEY,
            request_id INTEGER REFERENCES live_agent_requests(id),
            agent_email VARCHAR(100),
            user_email VARCHAR(100),
            status VARCHAR(50) DEFAULT 'active',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP
        )
    ''')

    # Create live_agent_messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_agent_messages (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES live_agent_sessions(id),
            sender_type VARCHAR(20),
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

def save_user_info(email, phone, country, status):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (email, phone, country, status) VALUES (%s, %s, %s, %s)
    """, (email, phone, country, status))
    conn.commit()
    conn.close()

def get_user_count():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT email) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def save_interaction(email, user_query, bot_response):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_history (email, user_query, bot_response)
        VALUES (%s, %s, %s)
    """, (email, user_query, bot_response))
    conn.commit()
    conn.close()

def user_exists(email, phone):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM users WHERE email = %s AND phone = %s
    """, (email, phone))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def update_user_with_tracking(email, status=None, description=None, updated_by_email=None):
    """
    Update user information and track who made the update
    """
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
        
        # Always update the updated_by and updated_at fields
        fields.append("updated_by = %s")
        values.append(updated_by_email)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        
        if not fields:
            return {"success": False, "message": "No fields to update"}
        
        values.append(email)
        query = f"UPDATE users SET {', '.join(fields)} WHERE LOWER(email) = LOWER(%s)"
        cursor.execute(query, tuple(values))
        
        if cursor.rowcount == 0:
            return {"success": False, "message": f"No chat user found with email '{email}'"}
        
        conn.commit()
        return {"success": True, "message": f"Chat user '{email}' updated successfully by {updated_by_email}"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close()

def get_user_update_history(email):
    """
    Get the update history for a specific user
    """
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT status, updated_by, updated_at 
            FROM users 
            WHERE LOWER(email) = LOWER(%s) AND updated_by IS NOT NULL
            ORDER BY updated_at DESC
        """, (email,))
        history = cursor.fetchall()
        return [
            {
                "status": row[0],
                "updated_by": row[1],
                "updated_at": row[2].isoformat() if row[2] else None
            }
            for row in history
        ]
    except Exception as e:
        return []
    finally:
        conn.close()

