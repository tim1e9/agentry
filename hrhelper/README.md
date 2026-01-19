# MCP Chatbot

A minimalist chatbot that integrates with an MCP (Model Context Protocol) server to provide
AI-powered assistance with calculator functionality (and future enterprise vacation/time-off queries).

## Features

- 🤖 OpenAI GPT-5 integration for natural language understanding
- 🔧 MCP over HTTP protocol support
- 💬 Clean, modern chat interface (vanilla HTML/CSS/JS)
- ⚡ Real-time tool calling and response

## Prerequisites

- Python 3.10+
- OpenAI API key
- MCP server running on `http://localhost:8000`

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-openai-api-key-here
MCP_SERVER_URL=http://localhost:8000
```

**Note:** If you are using a private PyPi server, please see `pip.conf.sample`.

### 3. Ensure MCP Server is Running

Make sure your MCP server is running on `http://localhost:8000` before starting the chatbot.

The server should expose the following MCP over HTTP endpoints:
- `POST /mcp/v1/initialize` - Initialize the connection
- `POST /mcp/v1/tools/list` - List available tools
- `POST /mcp/v1/tools/call` - Call a specific tool

## Running the Application

Start the Flask server:

```bash
python server.py
```

The application will be available at `http://localhost:3000`

## Usage

1. Open your browser and navigate to `http://localhost:3000`
2. Type a message in the chat input (e.g., "Hello, can you help me with my vacation scheduling?")
3. Press Enter or click Send
4. The bot will use the MCP server tools to calculate and respond

You can click "Show Available Tools" to see what tools are available from your MCP server.

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────┐
│   Browser   │─────▶│ Flask Server │─────▶│ OpenAI API │
│(HTML/CSS/JS)│◀─────│  (server.py) │◀─────│   (GPT-5)  │
└─────────────┘      └──────┬───────┘      └────────────┘
                            │
                            ▼
                     ┌───────────────┐
                     │  MCP Client   │
                     │(mcp_client.py)│
                     └──────┬────────┘
                            │
                            ▼
                     ┌────────────────┐
                     │  MCP Server    │
                     │(localhost:8000)│
                     └────────────────┘
```


## MCP Protocol

This chatbot uses the MCP over HTTP transport protocol (2024-11-05 version). The flow is:

1. Initialize connection with MCP server
2. Fetch available tools from the server
3. When user sends a message:
   - Forward to OpenAI with tool descriptions
   - If OpenAI wants to call a tool, forward the request to MCP server
   - Return MCP server response to OpenAI
   - Display final answer to user
