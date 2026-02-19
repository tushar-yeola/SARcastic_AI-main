FROM python:3.11-slim

WORKDIR /app

# Copy requirements from parent (if building from root context)
# We'll assume build context is root.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend ./backend

# Copy rules directory (needed for sar_service)
COPY rules ./rules

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
