from crewai import Crew, Process, Task
from agent_with_crewAI.agent import web_search_agent
from agent_with_crewAI.tools import search_tool

class SearchService:
    """Service class to handle web search queries using CrewAI agent"""
    
    @staticmethod
    def search_web(query: str, context: dict = None, max_results: int = 5):
        """
        Execute a web search using the CrewAI agent
        
        Args:
            query: The search query
            context: Additional context for the search
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        try:
            # Create a dynamic task for the search query
            search_task = Task(
                description=f"""Search the web for: {query}. 
Context: Objective: Accurate, actionable answer for a user in Madurai, Tamil Nadu, India.
Source preference: Official/government portals, standards bodies, reputable institutions, recognized media.
Output: 3-6 concise bullets with practical steps.
Exclusions: Ads, opinion pieces, outdated or non-Indian context unless needed for comparison.""",
                expected_output="Provide a clear and concise answer based on the search results",
                tools=[search_tool],
                agent=web_search_agent
            )
            
            # Create a crew with the agent and task
            crew = Crew(
                agents=[web_search_agent],
                tasks=[search_task],
                process=Process.sequential,
                verbose=True
            )
            
            # Execute the search
            result = crew.kickoff()
            
            return {
                "success": True,
                "query": query,
                "result": str(result),
                "context": context,
                "results": [str(result)]  # Add structured results for frontend
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
