# ComfyUI Studio

[简体中文](./README_CN.md) | English

A modern ComfyUI workflow management system with an intuitive web interface for managing, executing, and monitoring ComfyUI workflows.

## 📸 Screenshots

### Workflow Management
![Workflow Management](docs/images/home.png)

### Smart Creation & Task Queue
![Task Queue](docs/images/batch.png)

### System Monitor
![System Monitor](docs/images/monitor.png)

### Gallery
![Gallery](docs/images/gallery.png)

## ✨ Features

- 🎨 **Modern UI** - Beautiful interface built with React + TailwindCSS + shadcn/ui
- 📊 **Workflow Management** - Create, edit, import and export ComfyUI workflows
- 🚀 **Task Execution** - Execute workflows in real-time with progress monitoring
- 📈 **System Monitoring** - Real-time GPU, CPU, and memory usage monitoring
- 🔄 **WebSocket Support** - Real-time task status updates
- 📦 **Batch Processing** - Support for batch task management
- 🎯 **Node Visualization** - Workflow visualization using React Flow

## 🏗️ Tech Stack

### Backend
- **FastAPI** - High-performance async web framework
- **SQLAlchemy** - ORM for database operations
- **aiosqlite** - Async SQLite database
- **Pydantic** - Data validation
- **httpx** - Async HTTP client
- **WebSockets** - Real-time communication

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling framework
- **shadcn/ui** - UI component library
- **React Query** - Data fetching and caching
- **React Flow** - Workflow visualization
- **Zustand** - State management
- **Lucide React** - Icon library

## 📋 Prerequisites

- Python 3.12+
- Node.js 18+
- pnpm (recommended) or npm
- ComfyUI instance running at `http://127.0.0.1:8188`

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/opsworld30/comfy-studio.git
cd comfy-studio
```

### 2. Backend Setup

```bash
cd backend

# Install dependencies using uv (recommended)
uv sync

# Or use pip
pip install -e .

# Start backend server (config file is optional, defaults are provided)
uv run python main.py
# Or
uv run uvicorn app.main:app --reload --port 8000
```

Backend server will start at `http://localhost:8000`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install
# Or
npm install

# Start development server
pnpm dev
# Or
npm run dev
```

Frontend server will start at `http://localhost:5173`

## 📖 API Documentation

After starting the backend server, visit the following URLs to view API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 Configuration

### Backend Configuration

All backend configurations have default values. **No need to create a `.env` file to run**.

To customize configuration, create a `backend/.env` file:

```env
# ComfyUI service address (default: http://127.0.0.1:8188)
COMFYUI_URL=http://127.0.0.1:8188

# Database configuration (default: sqlite+aiosqlite:///./data/workflows.db)
DATABASE_URL=sqlite+aiosqlite:///./data/workflows.db

# Optional configurations
# LOG_LEVEL=INFO
# CORS_ORIGINS=["http://localhost:5173"]
```

See `backend/.env.example` for all configurable options.

### Frontend Configuration

Frontend connects to backend at `http://localhost:8000` by default. To modify, edit `frontend/src/config.ts`.

## 📁 Project Structure

```
comfy-studio/
├── backend/                 # Backend service
│   ├── app/
│   │   ├── routers/        # API routes
│   │   ├── services/       # Business logic
│   │   ├── middleware/     # Middleware
│   │   ├── models.py       # Data models
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── main.py         # Application entry
│   ├── data/               # Database files
│   ├── tests/              # Test files
│   ├── pyproject.toml      # Python project config
│   └── README.md
├── frontend/               # Frontend application
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom Hooks
│   │   ├── lib/            # Utility functions
│   │   └── App.tsx         # Application entry
│   ├── package.json
│   └── vite.config.ts
└── README.md               # Project documentation
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
uv run pytest
# With coverage
uv run pytest --cov=app tests/
```

### Frontend Tests

```bash
cd frontend
pnpm test
```

## 🏗️ Production Build

### Backend

```bash
cd backend
uv build
```

### Frontend

```bash
cd frontend
pnpm build
```

Build artifacts will be in the `frontend/dist/` directory.

## 📝 Development Guide

### Adding New API Endpoints

1. Create or edit route files in `backend/app/routers/`
2. Add business logic in `backend/app/services/`
3. Define request/response schemas in `backend/app/schemas.py`
4. Add data models in `backend/app/models.py` (if needed)

### Adding New Frontend Pages

1. Create page components in `frontend/src/pages/`
2. Add routes in `frontend/src/App.tsx`
3. Use React Query for data fetching
4. Build UI with shadcn/ui components

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📄 License

MIT License

## 🔗 Related Links

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [shadcn/ui](https://ui.shadcn.com/)

## ⚠️ Notes

- Ensure ComfyUI service is running and accessible
- Database will be created automatically on first run
- Database file is located at `backend/data/workflows.db`
- Uploaded workflow files are saved in the database

## 🐛 Troubleshooting

### Backend Cannot Connect to ComfyUI

Check if ComfyUI is running at `http://127.0.0.1:8188`, or modify `COMFYUI_URL` in `.env`.

### Frontend Cannot Connect to Backend

Ensure backend service is running at `http://localhost:8000`, check CORS configuration.

### Database Errors

Delete `backend/data/workflows.db` to reinitialize the database.

## 📧 Contact

For questions or suggestions, please submit an Issue.
