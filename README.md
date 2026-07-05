# Kiyanna Backend — AI Shopping Assistant & Virtual Try-On API 🛒✨

The backend power engine for **Kiyanna**, an advanced agentic e-commerce shopping assistant built for [Kapruka](https://www.kapruka.com). It combines multi-agent reasoning via **LangGraph**, live catalog search via **Model Context Protocol (MCP)**, and state-of-the-art **Virtual Try-On** capabilities powered by **fal.ai**.

---

## 🌟 Key Features

- **🧠 LangGraph Multi-Agent Workflow**:
  - **Router Node**: Intelligently categorizes user queries into shopping search, concierge assistance, checkout initiation, or order tracking.
  - **Shopper & Concierge Nodes**: Handles product recommendations, budget constraints, gift suggestions, and polite conversational guidance.
  - **Reflection & Self-Correction**: Automatically evaluates search results and refines queries if initial catalog lookups fall short.
- **🔌 Model Context Protocol (MCP) Integration**:
  - Direct real-time connection to Kapruka's e-commerce tools for live product catalog search, delivery city resolution, order placement, and status tracking.
- **👗 Virtual Try-On (fal.ai)**:
  - Powered by `fal-ai/kling/v1-5/kolors-virtual-try-on` using `fal_client`.
  - Enables users to upload full-body photos and virtually try on clothing items discovered during chat.
- **💾 Full-Stack Session & UI Persistence**:
  - File-based session storage (`data/sessions.json`) that persists complete chat histories across server restarts.
  - Saves not just text messages, but also **streamed reasoning steps (`thinking`)** and **Generative UI payloads (`ProductCarousel`, `OrderTimeline`, `PayLinkCard`)**.
- **⚡ Real-Time SSE Streaming**:
  - Uses Server-Sent Events (SSE) to stream word-by-word responses, live thinking processes, and dynamic UI cards directly to the frontend.
- **👁️ Multimodal Vision Support**:
  - Processes user-uploaded images via OpenRouter vision models for visual search and product matching.

---

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+)
- **Agent Framework**: [LangGraph](https://langchain-ai.github.io/langgraph/) & [LangChain](https://www.langchain.com/)
- **LLM / Vision Provider**: [OpenRouter](https://openrouter.ai/) (supporting Gemini, Claude, and GPT models)
- **AI Image & Try-On**: [fal.ai](https://fal.ai/) (`fal_client`)
- **Package Manager**: [uv](https://github.com/astral-sh/uv) / pip
- **Configuration**: Pydantic Settings & YAML (`config.yaml`)

---

## 🚀 Getting Started

### 1. Prerequisites

Ensure you have Python 3.11+ installed. We recommend using `uv` for lightning-fast dependency management:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Installation

Navigate to the backend directory and sync dependencies:

```bash
cd backend
uv sync
```

### 3. Environment Setup

Create a `.env` file in the `backend/` directory with the following API keys and settings:

```env
# OpenRouter (for LLM & Vision)
OPENROUTER_API_KEY="your_openrouter_api_key_here"

# fal.ai (for Virtual Try-On)
FAL_KEY="your_fal_api_key_here"

# Frontend URL (for CORS)
FRONTEND_URL="http://localhost:3000"

# Optional: Kapruka MCP Server URL (defaults to https://mcp.kapruka.com/mcp)
KAPRUKA_MCP_URL="https://mcp.kapruka.com/mcp"
```

### 4. Running the Development Server

Start the FastAPI server using `uvicorn`:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. You can access the interactive Swagger documentation at `http://localhost:8000/docs`.

---

## 📡 API Overview

### **Chat & Agent Streaming**
- `POST /api/v1/chat`: Initiates an SSE stream for chat conversations. Accepts message text, session ID, conversation history, shopping cart items, and optional image base64 payloads.

### **Session Management**
- `GET /api/v1/sessions`: Returns a list of all saved chat sessions with titles and timestamps.
- `GET /api/v1/sessions/{session_id}`: Retrieves complete session history, including restored `thinking` steps and `ui` component payloads.

### **Virtual Try-On**
- `POST /api/v1/tryon`: Submits a user photo and garment image URL to fal.ai for virtual try-on processing and returns the generated image URL.

### **E-Commerce & Checkout**
- `POST /api/v1/checkout`: Initiates order creation on Kapruka and generates payment links.
- `GET /api/v1/health`: Server health check endpoint.

---

## 📁 Project Structure

```text
backend/
├── app/
│   ├── agents/          # LangGraph state machine, nodes, and routing logic
│   ├── api/v1/          # FastAPI route handlers (chat, tryon, sessions, checkout)
│   ├── core/            # Config, database (SessionStore), prompt loader
│   ├── mcp/             # Kapruka Model Context Protocol client & tools
│   ├── prompts/         # Jinja2 prompt templates (shopper, concierge, vision)
│   └── main.py          # FastAPI application entry point & CORS setup
├── data/                # Persistent JSON storage (sessions.json, category caches)
├── config.yaml          # Model selection, timeouts, and system parameters
└── pyproject.toml       # Python dependencies and project metadata
```
