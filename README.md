# 🚗 Car Diagnosis System

**AI-Powered Vehicle Complaint Analysis & Diagnosis**

A comprehensive system that uses machine learning and multi-modal AI to diagnose car issues, chat with virtual mechanics, and track vehicle history.

---

## ✨ Features

- 🤖 **AI Complaint Classification** - Automatic categorization with 98% accuracy
- 💬 **Smart Chat** - Multi-modal AI mechanic (text + images via LLaVA)
- 📚 **RAG System** - Search 376+ car manuals for relevant information
- 🔍 **History Search** - Track all complaints by license plate
- 📸 **Image Analysis** - Upload car issue photos for AI diagnosis
- 🎨 **Modern UI** - Automotive-themed design with React

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop
- Node.js 20+
- Ollama (optional, for local LLM)

### 1. Clone & Setup
```bash
git clone <repo-url>
cd car--issues
```

### 2. Environment Configuration
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
GROQ_API_KEY=your_groq_key_here
```

### 3. Start Backend (Docker)
```bash
docker compose up -d
```

### 4. Start Frontend (Development)
```bash
cd frontend
npm install
npm run dev
```

### 5. Access
- **Frontend**: http://localhost:5173
- **API**: http://localhost:8000/api/v1/
- **Admin**: http://localhost:8000/admin/

---

## 📁 Project Structure

```
car--issues/
├── backend/              # Django REST API
├── frontend/             # React + Vite + Tailwind
├── rag data/             # Car manuals (376 PDFs)
├── docker-compose.yml    # Services orchestration
└── .env                  # Environment variables
```

---

## 🤖 AI Models

| Model | Purpose | Size | Location |
|-------|---------|------|----------|
| the_model.h5 | Complaint Classification | 803 MB | Local |
| all-MiniLM-L6-v2 | Text Embeddings | 90 MB | Cached |
| CLIP ViT-B-32 | Image Embeddings | 300 MB | Cached |
| LLaVA | Multi-modal LLM | 4.5 GB | Ollama |
| Qwen3-32B | Chat LLM | - | GROQ API |

---

## 📡 API Endpoints

### Complaints
- `POST /api/v1/complaints/quick-submit/` - Submit complaint
- `GET /api/v1/complaints/` - List complaints

### Chat
- `POST /api/v1/chat/sessions/` - Create chat session
- `POST /api/v1/chat/sessions/{id}/send_message/` - Send message (+ images)

### Search
- `GET /api/v1/cars/by_license_plate/?plate=ABC123` - Search by plate
- `GET /api/v1/cars/{id}/complaint_history/` - Get history

---

## 🛠️ Tech Stack

**Backend:**
- Django 5.0 + DRF
- PostgreSQL 15
- Redis 7 + Celery
- TensorFlow, LangChain
- Docker

**Frontend:**
- React 18 + Vite
- Tailwind CSS
- React Router v6

**AI/ML:**
- TensorFlow/Keras
- LangChain + FAISS
- HuggingFace Transformers
- Ollama (LLaVA)
- GROQ API

---

## 📚 Documentation

- [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md) - Complete project overview
- [`startup_guide.md`](./startup_guide.md) - Detailed setup instructions
- [`design_system.md`](./design_system.md) - UI/UX guidelines
- [`frontend/README.md`](./frontend/README.md) - Frontend documentation

---

## 🐛 Troubleshooting

### Frontend not loading?
```bash
# Check if Vite is running
cd frontend
npm run dev
```

### Backend not responding?
```bash
# Check Docker containers
docker compose ps
docker compose logs backend
```

### Chat not working?
```bash
# Verify Ollama is running
ollama serve
ollama list

# Check GROQ API key in .env
```

---

## 🔧 Development

### Run Tests
```bash
# Backend
docker compose exec backend python manage.py test

# Frontend
cd frontend
npm run build  # Check for errors
```

### View Logs
```bash
docker compose logs -f backend
docker compose logs -f celery
```

### Reset Database
```bash
docker compose down -v
docker compose up -d
docker compose exec backend python manage.py migrate
```

---

## 📦 Dependencies

- **Backend**: 81 Python packages
- **Frontend**: 329 npm packages
- **ML Models**: ~6 GB total

---

## 🔐 Security Notes

- Never commit `.env` file
- Use strong `SECRET_KEY` in production
- Enable SSL/TLS for production
- Set `DEBUG=False` in production
- Configure proper CORS origins

---

## 📊 Performance

- First Load: < 2s
- API Response: < 500ms
- Classification: < 1s
- RAG Query: 2-5s
- Chat: 3-10s (streaming)

---

## 🎨 Design

**Automotive Theme** inspired by luxury car dashboards:
- Carbon fiber textures
- LED effects
- Metallic gradients
- Electric cyan accents
- Racing red CTAs

---

## 📝 License

[Your License Here]

---

## 👥 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open pull request

---

## 🆘 Support

For issues or questions:
1. Check documentation files
2. Review logs: `docker compose logs`
3. Open an issue on GitHub

---

## 🎯 Roadmap

- [ ] Mobile app (React Native)
- [ ] Admin dashboard enhancements
- [ ] Multi-language support
- [ ] Analytics & reporting
- [ ] PWA support

---

**Built with ❤️ using AI & Modern Web Technologies**
