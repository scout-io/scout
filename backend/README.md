# Scout Backend

A FastAPI-based backend service for multi-armed bandit (MAB) experimentation and A/B testing.

## Features

- Multi-armed bandit model management
- Contextual bandit support
- Redis-based model storage
- Prometheus metrics integration
- API protection with token authentication
- Admin configuration endpoints
- Health monitoring

## Project Structure

```
backend/
├── app/
│   ├── api/            # API endpoints
│   ├── core/           # Core configuration
│   ├── db/             # Database connections
│   ├── models/         # Data models
│   ├── schemas/        # Pydantic schemas
│   ├── services/       # Business logic
│   └── utils/          # Utility functions
├── requirements.txt    # Project dependencies
└── README.md          # This file
```

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your configuration:
   ```env
   HOST=127.0.0.1
   PORT=8000
   DEBUG=false
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_CONTEXT_TTL=86400
   ```

4. Start Redis server (if not already running):
   ```bash
   redis-server
   ```

5. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

- `POST /api/v1/create_model`: Create a new MAB model
- `POST /api/v1/update_model/{model_id}`: Update model with new data
- `POST /api/v1/fetch_recommended_variant`: Get model recommendation
- `GET /api/v1/models`: List all models
- `GET /metrics`: Prometheus metrics
- `GET /health`: Health check

## Development

### Running Tests

```bash
pytest
```

### Code Style

This project uses:
- Black for code formatting
- isort for import sorting
- flake8 for linting

To format code:
```bash
black .
isort .
```

### Docker Support

Build and run with Docker:
```bash
docker build -t scout-backend .
docker run -p 8000:8000 scout-backend
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 