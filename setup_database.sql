-- PostgreSQL Database Setup Script
-- Database: faqq_db
-- Username: vasala
-- Password: Vasala@#66118

-- Connect to the database (run this in psql or pgAdmin)
-- \c faqq_db

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert the specified user
INSERT INTO users (username, phone_number) 
VALUES ('vasala', '8688714580')
ON CONFLICT (username) DO NOTHING;

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number);

-- Verify the data
SELECT * FROM users WHERE username = 'vasala';

-- Optional: Create additional tables for FAQ system
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by VARCHAR(100),
    file_path VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    user_phone VARCHAR(20),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    document_source VARCHAR(255)
);

-- Grant permissions to vasala user
GRANT ALL PRIVILEGES ON TABLE users TO vasala;
GRANT ALL PRIVILEGES ON TABLE documents TO vasala;
GRANT ALL PRIVILEGES ON TABLE chat_history TO vasala;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vasala; 