# Car Diagnosis System - Frontend

Modern React frontend with automotive theme.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

## 🎨 Features

- ✨ Automotive-themed UI with carbon fiber effects
- 🚗 AI-powered complaint diagnosis
- 💬 Chat with LLaVA (multi-modal AI)
- 📸 Image upload support
- 🔍 Vehicle history search
- ⚡ Fast & responsive with Vite
- 🎨 Tailwind CSS for styling

## 📁 Structure

```
src/
├── components/
│   ├── layout/      # Navbar, Footer
│   ├── home/        # Hero section
│   └── ui/          # Reusable components
├── pages/           # Route pages
├── services/        # API client
└── App.jsx          # Main app with routing
```

## 🎯 Routes

- `/` - Home page
- `/complaint` - Submit complaint
- `/chat` - Chat with AI
- `/search` - Search vehicle history

## 🔧 Tech Stack

- React 18
- Vite
- React Router v6
- Tailwind CSS
- Automotive Design System

## 🌐 API

The frontend connects to the Django backend at `/api/v1/`.

Make sure the backend is running on the same domain or configure CORS properly.
