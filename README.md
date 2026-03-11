# Investment Bot Agentic App ✨

Turkish investment advisory bot using FastAPI + Azure OpenAI GPT-5.1 + Next.js with streaming chat and intelligent tool calling.

## 📋 Overview

An intelligent investment bot that helps customers with Turkish mutual fund queries using:
- **Backend**: FastAPI with Azure OpenAI GPT-5.1 function calling
- **Frontend**: Next.js 14 with Server-Sent Events (SSE) streaming
- **Tools**: Fund knowledge base search and customer transaction retrieval
- **Theme**: Dark green (#006837) and white professional design

## 🏗️ Architecture

```
┌─────────────┐         ┌──────────────────┐         ┌───────────────┐
│   Next.js   │  SSE    │   FastAPI        │  API    │  Azure OpenAI │
│   Frontend  │ ◄─────► │   Backend        │ ◄─────► │   GPT-5.1     │
│  (Port 3000)│         │   (Port 8000)    │         └───────────────┘
└─────────────┘         └──────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Tool System │
                        ├──────────────┤
                        │ • Fund KB    │
                        │ • Transactions│
                        │ • Customer Info│
                        └──────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Azure OpenAI API access with GPT-5.1 deployment

### Backend Setup

1. **Navigate to backend directory**:
   ```powershell
   cd backend
   ```

2. **Create and activate virtual environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```powershell
   cp .env.example .env
   ```
   
   Edit `.env` and add your Azure OpenAI credentials:
   ```env
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_KEY=your-azure-openai-key-here
   AZURE_OPENAI_DEPLOYMENT=gpt-5.1
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

5. **Run the FastAPI server**:
   ```powershell
   python main.py
   ```
   
   Backend will be available at: `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**:
   ```powershell
   cd frontend
   ```

2. **Install dependencies**:
   ```powershell
   npm install
   ```

3. **Configure environment variables**:
   ```powershell
   cp .env.example .env.local
   ```
   
   Edit `.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. **Run the development server**:
   ```powershell
   npm run dev
   ```
   
   Frontend will be available at: `http://localhost:3000`


## 🎨 UI Features

- **Dark Green Theme**: Professional Bank colors (#006837, #00573D)
- **Streaming Responses**: Real-time SSE streaming with typing indicators
- **Debug Tooltips**: Information icons show:
  - Tool calls and arguments
  - Execution times
  - Debug metadata
- **Conversation History**: Maintains context for follow-up questions
- **Example Questions**: Quick-start buttons for common queries
- **Responsive Design**: Works on desktop and mobile

## 📁 Project Structure

```
maf-demo-app/
├── backend/
│   ├── agent/
│   │   ├── __init__.py
│   │   └── investment_agent.py     # Main agent with GPT-5.1
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py                 # Dummy user model
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── fund_knowledge.py       # Fund information tool
│   │   └── customer_transactions.py # Transaction tool
│   ├── main.py                     # FastAPI app with SSE
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                # Main chat interface
│   │   └── globals.css
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── .env.example
└── README.md
```

## 🔐 Security Notes

- **No Authentication**: Currently uses dummy user
- **No Database**: All data is in-memory and resets on restart
- **Development Only**: Not production-ready
- **API Keys**: Keep your `.env` files secure and never commit them

## 📡 API Endpoints

### Backend (FastAPI)

- `GET /` - Health check
- `POST /chat/stream` - Streaming chat with SSE
  ```json
  {
    "message": "GTA Fonu nedir?",
    "session_id": "default"
  }
  ```
- `POST /chat` - Non-streaming chat (for testing)
- `DELETE /session/{session_id}` - Clear conversation history

### SSE Event Format

Events are streamed in this format:
```json
{
  "type": "message" | "tool_call" | "tool_result" | "thinking" | "error" | "done",
  "data": { ... },
  "debug": { ... }
}
```

## 🐛 Debugging

### Check Backend Logs
```powershell
# Backend terminal shows request/response logs
# Watch for tool executions and Azure OpenAI calls
```

### View Debug Information
- Click the **ℹ️ information icon** on any assistant message
- View tool calls, execution times, and metadata
- See full debug JSON in the tooltip

### Common Issues

1. **"Network response was not ok"**
   - Ensure backend is running on port 8000
   - Check `NEXT_PUBLIC_API_URL` in frontend `.env.local`

2. **"Azure OpenAI Error"**
   - Verify API key and endpoint in backend `.env`
   - Ensure deployment name is exactly "gpt-5.1"

3. **"Fon bulunamadı" (Fund not found)**
   - Use exact fund codes: GTA, GOL, or GTL

## 🚧 Future Enhancements

- [ ] Add user authentication (Azure AD B2C)
- [ ] Implement database for persistent storage
- [ ] Add more funds and real-time market data
- [ ] Support file uploads (documents, reports)
- [ ] Multi-language support (English, Turkish)
- [ ] Voice input/output capabilities
- [ ] Advanced portfolio analytics
- [ ] Real-time notifications

## 📄 License

This is a demo application for educational purposes.

## 🤝 Support

For questions or issues, please check:
- Backend logs in terminal
- Browser console (F12) for frontend errors
- Debug tooltips in chat interface

---

**Built with ❤️ using FastAPI, Next.js, and Azure OpenAI GPT-5.1**
