-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create use_cases table
CREATE TABLE IF NOT EXISTS use_cases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    uri_context VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255),
    description TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_use_cases_name ON use_cases(name);
CREATE INDEX IF NOT EXISTS idx_use_cases_uri_context ON use_cases(uri_context);

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    use_case_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'processing',
    FOREIGN KEY (use_case_id) REFERENCES use_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_use_case_id ON documents(use_case_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- Create document_chunks table with vector support
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI text-embedding-3-small produces 1536-dimensional vectors
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- Create conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    use_case_id INTEGER NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (use_case_id) REFERENCES use_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversations_use_case_id ON conversations(use_case_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Insert default use cases
INSERT INTO use_cases (id, name, uri_context, title, description, details) VALUES
(1, 'Squad Navigator', 'squad-navigator', 'Squad Navigator', 'Welcome to Squad Navigator use case.', 'Navigate through your squads and manage team collaboration effectively.'),
(2, 'Chapter Explorer', 'chapter-explorer', 'Chapter Explorer', 'Welcome to Chapter Explorer use case.', 'Explore chapters and discover insights across different organizational units.'),
(3, 'Guild Convener', 'guild-convener', 'Guild Convener', 'Welcome to Guild Convener use case.', 'Convene guilds and facilitate cross-functional collaboration.')
ON CONFLICT (id) DO NOTHING;
