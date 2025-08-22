from crewai import Task
from tools import search_tool
from agent import web_search_agent



user_task = input("Enter your search query: ")
max_tokens = 100

task_web = Task(
    description=(
        f"Search the web for the best answer to the user's question: {user_task}. "
+       f"Provide accurate and concise information."
),
    expected_output=f"Provide a clear and concise answer in 2-3 lines. Limit response to {max_tokens} tokens.",
    tools=[search_tool],
    agent=web_search_agent
)
