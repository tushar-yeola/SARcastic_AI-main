CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL
);

CREATE TABLE sar_cases (
    id SERIAL PRIMARY KEY,
    analyst_id INT REFERENCES users(id),
    customer_name VARCHAR(255),
    kyc_data TEXT,
    transaction_data TEXT,
    generated_narrative TEXT,
    edited_narrative TEXT,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    sar_id INT REFERENCES sar_cases(id),
    rules_triggered TEXT,
    llm_prompt TEXT,
    llm_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
