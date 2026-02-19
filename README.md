# SARcastic AI MVP

## Installation & Setup

1. **Environment Setup**
   Ensure `.env` file is present in root with:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=sarcastic_ai_db
   DB_USER=postgres
   DB_PASSWORD=admin123
   OLLAMA_MODEL=llama3
   CHROMA_SERVER_HOST=localhost
   CHROMA_SERVER_PORT=8000
   API_URL=http://localhost:8000/api/v1
   ```

2. **Docker Compose (Recommended)**
   Run the full stack:
   ```bash
   docker-compose up --build
   ```

3. **Seeding Data**
   After containers are up, seed the database:
   ```bash
   docker-compose exec backend python -m backend.scripts.seed
   ```

## Development (Local)

1. **Backend**
   ```bash
   pip install -r requirements.txt
   uvicorn backend.main:app --reload --port 8000
   ```

2. **Frontend**
   ```bash
   streamlit run compliance_dashboard.py
   ```

## Architecture

- **Backend**: FastAPI (Rest API), SQLAlchemy (Pooling), ChromaDB (Vector), JWT Auth.
- **Frontend**: Streamlit (Pure UI, calls Backend via API).
- **Services**: Segregated business logic in `backend/services`.
- **Database**: PostgreSQL.

## API Documentation
Access Swagger UI at `http://localhost:8000/docs`.

## Access Application:
Frontend: http://localhost:8501
API Docs: http://localhost:8000/docs

## Login Credentials (From Database)
Email	Password	Role
admin@sarcastic.ai	admin123	Compliance Head
sarah@sarcastic.ai	sarah123	Analyst
mike@sarcastic.ai	mike123	Reviewer
jane@sarcastic.ai	jane123	MLRO
david@sarcastic.ai	david123	Analyst
auditor@sarcastic.ai	audit123	Auditor
