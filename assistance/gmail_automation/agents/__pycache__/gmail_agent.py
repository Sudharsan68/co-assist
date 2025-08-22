from browser_use.llm import ChatGroq
from utils.env_loader import load_env
import json
import re

class GmailAgent:
    def __init__(self, groq_api_key, model="meta-llama/llama-4-maverick-17b-128e-instruct"):
        self.llm = ChatGroq(model=model, api_key=groq_api_key)
        self.env = load_env()

    def login_instruction(self):
        """Return a natural language instruction for logging in"""
        return f"Log in to Gmail using {self.env['GMAIL_EMAIL']} and handle 2FA if prompted."

    def parse_task(self, task: str) -> str:
        """Parse task into JSON email data"""
        task_lower = task.lower()
        
        if "send" in task_lower and "email" in task_lower:
            # Extract email details using regex
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', task)
            email = email_match.group(0) if email_match else "recipient@example.com"
            
            subject_match = re.search(r'subject ["\'](.*?)["\']', task)
            subject = subject_match.group(1) if subject_match else "No Subject"
            
            body_match = re.search(r'body ["\'](.*?)["\']', task)
            body = body_match.group(1) if body_match else "No Body"
            
            # Return JSON string
            return json.dumps({
                "to": email,
                "subject": subject,
                "body": body
            })
        
        return json.dumps({
            "to": "",
            "subject": "",
            "body": f"Manual steps needed for: {task}"
        })