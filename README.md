# Conversational Agentic Bot

## Quick Start

**Prerequisites:**
- Python 3.13+
- Node.js 16+
- OpenAI API Key
- Docker & Docker Compose (for PostgreSQL)

**Setup:**
1. Start PostgreSQL with pgvector:
   ```bash
   docker-compose up -d
   ```

2. Copy the backend environment file:
   ```bash
   cp backend/.env.example backend/.env
   ```

3. Add your OpenAI API key to `backend/.env`

To start both backend and frontend servers with one command:

```bash
./start.sh
```

This script will:
- Create a Python virtual environment in the backend directory (if it doesn't exist)
- Install backend dependencies
- Initialize and seed the database with use cases
- Start the FastAPI server on http://localhost:8000
- Install frontend dependencies (if needed)
- Start the React development server on http://localhost:5173

Press `Ctrl+C` to stop both servers.

## Database Management

The application uses SQLite to store use case data. The database file is located at `db/use_cases.db`.

### Seed Database Manually

To initialize or reseed the database:

```bash
cd backend
source venv/bin/activate
python seed_db.py
```

### Database Schema

**use_cases** table:
- `id`: Serial (Primary Key)
- `name`: VARCHAR(255) (Unique, Indexed)
- `uri_context`: VARCHAR(255) (Unique, Indexed) - URL-friendly slug
- `title`: VARCHAR(255) - Display title
- `description`: TEXT - Short description
- `details`: TEXT - Detailed information
- `created_at`: TIMESTAMP

**documents** table:
- `id`: Serial (Primary Key)
- `use_case_id`: INTEGER (Foreign Key)
- `filename`: VARCHAR(255)
- `file_path`: VARCHAR(512)
- `file_size`: INTEGER
- `uploaded_at`: TIMESTAMP
- `status`: VARCHAR(50)

**document_chunks** table:
- `id`: Serial (Primary Key)
- `document_id`: INTEGER (Foreign Key)
- `chunk_index`: INTEGER
- `content`: TEXT
- `embedding`: VECTOR(1536) - pgvector type for embeddings
- `created_at`: TIMESTAMP

## Manual Setup

### Backend (FastAPI)
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize database:
   ```bash
   python seed_db.py
   ```

5. Run the FastAPI server:
   ```bash
   python main.py
   ```
   Or with uvicorn directly:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

The backend will be available at http://localhost:8000

### Frontend (React + Vite)
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies (if not already done):
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
- **Database**: PostgreSQL 16 with pgvector extension for vector storage
- **Frontend**: React with React Router for navigation
- **Vector Storage**: PostgreSQL pgvectorext}` - Returns detailed information about a specific use case

## Architecture

- **Backend**: FastAPI with SQLAlchemy ORM and SQLite database
- **Frontend**: React with React Router for navigation
- **Database**: SQLite for persistent storage of use case data
- **Vector Database**: ChromaDB for document embeddings
- **LLM**: OpenAI GPT for embeddings (text-embedding-3-small)
- **Routing**: Dynamic routing pattern `/usecase/:usecase-id`

All use case data is stored in the database, making the system fully dynamic with no hardcoded use case information in the code.

## Document Upload Feature

Users can upload documentdirectly in PostgreSQL using pgvector
7. Metadata is stored in PostgreSQL database

### Database Tables
- `use_cases`: Core use case information
- `documents`: Uploaded document metadata
- `document_chunks`: Individual text chunks with vector embeddings stored using pgvector
### Supported File Types
- PDF (.pdf)
- Text files (.txt)
- Markdown files (.md)

### Document Processing Pipeline
1. User uploads document via sidebar → Upload Documents
2. File is saved to `backend/uploads/{use_case_id}/`
3. Text is extracted based on file type
4. Text is chunked using RecursiveCharacterTextSplitter (1000 chars, 200 overlap)
5. Each chunk is embedded using OpenAI API
6. Embeddings are stored in ChromaDB collection per use case
7. Metadata is stored in SQLite database

### Database Tables
- `use_cases`: Core use case information
- `documents`: Uploaded document metadata
- `document_chunks`: Individual text chunks with references to vector DB embeddings

- `GET /api/use-cases` - Returns the list of available use cases:
  - Squad Navigator
  - Chapter Explorer
  - Guild Convener
