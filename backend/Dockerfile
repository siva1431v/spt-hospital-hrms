FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2, pdfplumber, reportlab, and health checks
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libmupdf-dev \
    libfreetype6-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads/pdfs /app/uploads/salary_slips

# Make startup script executable
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
