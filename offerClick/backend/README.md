# OfferClick Backend

FastAPI backend for the OfferClick job application assistant.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python run.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Data

Jobs are read from `../data/screened_jobs.json` (relative to backend directory).

## Converter Integration

To integrate with your real converter module:

1. Update `app/services/converter.py`
2. Replace the mock `generate_resume_for_job` function with your implementation
3. Ensure the return signature matches:
```python
{
    "pdf_path": str,
    "text_path": str,
    "version_id": str,
    "created_at": str  # ISO timestamp
}
```

