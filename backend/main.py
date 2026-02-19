from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.routers import auth, dashboard, cases
from backend.database import engine
# Pre-start checks could go here

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Startup Event to Ensure DB Schema
@app.on_event("startup")
def startup_db_client():
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            # Check/Create Sar Details Table for Annexure II
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sar_details (
                    id SERIAL PRIMARY KEY,
                    case_id INT REFERENCES sar_cases(id) ON DELETE CASCADE,
                    internal_ref_id UUID,
                    risk_score VARCHAR(20),
                    part_a JSONB DEFAULT '{}',
                    part_b_narrative TEXT,
                    part_c JSONB DEFAULT '{}',
                    part_d JSONB DEFAULT '[]',
                    part_e1_person JSONB DEFAULT '{}',
                    part_e2_accounts JSONB DEFAULT '[]',
                    part_e3_entity JSONB DEFAULT '{}',
                    part_f_goods JSONB DEFAULT '{}',
                    full_report JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sar_details_case_id ON sar_details(case_id);

                -- Ensure sar_cases has necessary columns
                ALTER TABLE sar_cases ADD COLUMN IF NOT EXISTS internal_ref_id UUID;
                ALTER TABLE sar_cases ADD COLUMN IF NOT EXISTS risk_score VARCHAR(20);
                
                -- Check/Create Transactions Table
                CREATE TABLE IF NOT EXISTS transactions (
                    id UUID PRIMARY KEY,
                    case_id INT REFERENCES sar_cases(id) ON DELETE CASCADE,
                    customer_id VARCHAR(255) NOT NULL,
                    transaction_date TIMESTAMP NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    type VARCHAR(50),
                    description TEXT,
                    merchant VARCHAR(255),
                    currency VARCHAR(10) DEFAULT 'USD',
                    country VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_transactions_case_id ON transactions(case_id);
            """))
            print("Database schema verified (Transactions & SAR Details).")
    except Exception as e:
        print(f"Database startup error: {e}")

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["dashboard"])
app.include_router(cases.router, prefix=f"{settings.API_V1_STR}/cases", tags=["cases"])

@app.get("/")
def root():
    return {"message": "Welcome to SARcastic AI API"}
