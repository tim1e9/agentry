"""
Chat service for handling the interactions with MCP
"""
import os
import json
from datetime import datetime
from openai import OpenAI
from mcp_client import MCPClient

import logging


logger = logging.getLogger(__name__)

# Conversation history limits
MAX_CONVERSATION_MESSAGES = int(os.getenv('MAX_CONVERSATION_MESSAGES', '20'))  # Keep last N messages (plus system prompt)

class ChatService:
  """Service for interacting with the LLM"""
  
  def __init__(self):
    self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    self.mcp_client = MCPClient(os.getenv('MCP_SERVER_URL'))
    # OpenAI model selection
    self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # Initialize MCP connection and get available tools

  def rev_engines(self):
    self.mcp_tools = []
    init_result = self.mcp_client.initialize()
    logger.info(f"MCP Tooling initialized: {str(init_result)}")

  def trim_conversation_history(self, history, max_messages=MAX_CONVERSATION_MESSAGES):
    """
    Trim conversation history to keep only recent messages.
    Always preserves the system prompt (first message).
    
    Args:
        history: List of conversation messages
        max_messages: Maximum number of messages to keep (not counting system prompt)
    
    Returns:
        Trimmed history list
    """
    if len(history) <= max_messages + 1:  # +1 for system prompt
        return history
    
    # Keep system prompt + last N messages
    return [history[0]] + history[-(max_messages):]

  def get_tools(self, access_token: str):
     return self.mcp_client.list_tools(access_token=access_token)

  def get_initial_prompt(self):
    # Note: LLMs have trouble figuring out the current date. Help them.
    CUR_YEAR = str(datetime.now().year)
    INITIAL_PROMPT = f"""
    You are a professional HR assistant helping employees manage their vacation time and understand HR policies.
    Be friendly, professional, and clear. When processing vacation requests, always confirm details with the user
    before finalizing. Respect company policies and inform users of any limitations or conflicts. Use the available
    tools to help employees with their HR needs. Please note that you can combine actions to create new functionality.
    For example, you can move a vacation by deleting an existing one and creating a new one. All basic operations are
    supported via tooling: add, update, view, and delete.
    The current year is: {CUR_YEAR}
    """
    return INITIAL_PROMPT
  


  def chat(self, employee_id, user_tools, messages, access_token):
    # Convert MCP tools to OpenAI function format
    openai_tools = []
    for tool in user_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})
            }
        })

    # Call OpenAI with tools
    response = self.openai_client.chat.completions.create(
        model=self.OPENAI_MODEL,
        messages=messages,
        tools=openai_tools if openai_tools else None,
        tool_choice="auto" if openai_tools else None
    )

    assistant_message = response.choices[0].message

    # Check if the model wants to call a tool
    if assistant_message.tool_calls:
        # Process tool calls
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            # Inject employee_id from authenticated user if not already present
            if 'employee_id' not in function_args and employee_id:
                function_args['employee_id'] = employee_id
            
            logger.info("Calling tool: %s", function_name)
            logger.info("Tool args for %s: %s", function_name, function_args)
            # Forward the user's access token to the MCP server
            tool_result = self.mcp_client.call_tool(function_name, function_args, access_token=access_token)
            logger.debug("Tool result for %s: %s", function_name, tool_result)
            new_message = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result)
            }
            messages.append(new_message)
        
        # Get final response from OpenAI
        final_response = self.openai_client.chat.completions.create(
            model=self.OPENAI_MODEL,
            messages=messages
        )
        
        final_message_txt = final_response.choices[0].message.content
    else:
        final_message_txt = assistant_message.content
    
    final_message = {
       "role": "assistant",
       "content": final_message_txt
    }
    messages.append(final_message)

    trimmed_messages = self.trim_conversation_history(messages)

    return trimmed_messages
  

