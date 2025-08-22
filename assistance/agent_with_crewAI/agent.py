import os
from dotenv import load_dotenv
from crewai import Agent, LLM
from crewai_tools import SerperDevTool
search_tool = SerperDevTool()

# Load env
load_dotenv()
api_key = os.environ.get("OPEN_ROUTER")

# LLM
llm = LLM(
    model="openrouter/anthropic/claude-3.5-sonnet",
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
    max_tokens=100  # Add token limit to reduce cost
)

web_search_agent = Agent(
    role="Web Search Agent",
    tools=[search_tool],
    goal=("Find most accurate to users query"),
    backstory=("user search for the best answer"),
    verbose=True,
    allow_delegation=True,
    llm=llm
)
