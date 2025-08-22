import sys
if sys.platform.startswith("win"):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright
from gmail_automation.utils.env_loader import load_env as load_gmail_env
from gmail_automation.agents.gmail_agent import GmailAgent
from datetime import datetime
import json, os, time, sys

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------- Async Utilities --------
async def save_screenshot(page, label="after_action"):
    """Async screenshot capture with proper error handling"""
    try:
        os.makedirs("screens", exist_ok=True)
        path = f"screens/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}.png"
        await page.screenshot(path=path, full_page=True)
        return path
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}")
        return None

async def login(page, env):
    """Async Gmail login with proper waiting"""
    try:
        await page.goto("https://mail.google.com", wait_until="domcontentloaded")
        await page.wait_for_selector("div[gh='cm']", timeout=120_000)
        await page.wait_for_selector("div[role='main']", timeout=60_000)
        logger.info("✅ Gmail session loaded via Chrome profile")
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise

async def preview_email(email_data):
    """Preview email data"""
    logger.info("\n===== EMAIL PREVIEW =====")
    logger.info(f"To:    {', '.join(email_data.get('to', []))}")
    if email_data.get("cc"): logger.info(f"Cc:    {', '.join(email_data['cc'])}")
    if email_data.get("bcc"): logger.info(f"Bcc:   {', '.join(email_data['bcc'])}")
    logger.info(f"Subject: {email_data['subject']}")
    logger.info(f"Body:\n{email_data['body']}")
    logger.info("========================\n")

async def wait_for_element(page, selector, timeout=10000, description="element"):
    """Enhanced element waiting with multiple strategies"""
    try:
        # Try multiple selector strategies
        selectors = [selector] if isinstance(selector, str) else selector
        
        for sel in selectors:
            try:
                element = page.locator(sel).first
                await element.wait_for(state="visible", timeout=timeout//len(selectors))
                return element
            except:
                continue
        
        # If all selectors fail, try waiting for any textbox in the dialog
        dialog = page.locator("div[role='dialog']")
        if await dialog.count() > 0:
            textboxes = dialog.locator("[contenteditable='true'], input[type='text'], textarea")
            if await textboxes.count() > 0:
                return textboxes.first
        
        raise TimeoutError(f"Could not find {description}")
    except Exception as e:
        logger.error(f"Error waiting for {description}: {e}")
        raise

async def fill_field_with_retry(page, field_type, value, max_retries=3):
    """Fill a field with retry logic"""
    for attempt in range(max_retries):
        try:
            if field_type == "to":
                selectors = [
                    "input[aria-label='To']",
                    "input[name='to']",
                    "div[aria-label='To'] input",
                    "input[email]"
                ]
                field = await wait_for_element(page, selectors, 5000, "To field")
            elif field_type == "subject":
                selectors = ["input[name='subjectbox']", "input[aria-label='Subject']"]
                field = await wait_for_element(page, selectors, 5000, "Subject field")
            elif field_type == "body":
                selectors = [
                    "div[aria-label='Message Body']",
                    "div[contenteditable='true']",
                    "div[role='textbox']"
                ]
                field = await wait_for_element(page, selectors, 5000, "Message body")
            
            await field.click()
            await field.clear()
            await field.fill(str(value))
            return True
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            logger.warning(f"Retry {attempt + 1} for {field_type}: {e}")
            await asyncio.sleep(1)
    
    return False

async def send_email(page, email_data):
    """Async email sending with comprehensive error handling and retries"""
    logger.info(f"📩 Sending email: {email_data['to']} - {email_data['subject']}")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Click compose button with retry
            compose_btn = await wait_for_element(page, "div[gh='cm']", 10000, "compose button")
            await compose_btn.click()
            
            # Wait for compose dialog
            await wait_for_element(page, "div[role='dialog']", 10000, "compose dialog")
            await asyncio.sleep(1)  # Brief pause for stability
            
            # Fill recipients
            to_emails = email_data["to"] if isinstance(email_data["to"], list) else [email_data["to"]]
            for email in to_emails:
                to_field = await wait_for_element(page, [
                    "input[aria-label='To']",
                    "input[name='to']",
                    "div[aria-label='To'] input"
                ], 5000, "To field")
                await to_field.click()
                await to_field.fill(email)
                await page.keyboard.press("Enter")
            
            # Fill CC if provided
            if email_data.get("cc"):
                cc_emails = email_data["cc"] if isinstance(email_data["cc"], list) else [email_data["cc"]]
                for email in cc_emails:
                    cc_field = await wait_for_element(page, [
                        "input[aria-label='Cc']",
                        "input[name='cc']"
                    ], 5000, "Cc field")
                    await cc_field.click()
                    await cc_field.fill(email)
                    await page.keyboard.press("Enter")
            
            # Fill BCC if provided
            if email_data.get("bcc"):
                bcc_emails = email_data["bcc"] if isinstance(email_data["bcc"], list) else [email_data["bcc"]]
                for email in bcc_emails:
                    bcc_field = await wait_for_element(page, [
                        "input[aria-label='Bcc']",
                        "input[name='bcc']"
                    ], 5000, "Bcc field")
                    await bcc_field.click()
                    await bcc_field.fill(email)
                    await page.keyboard.press("Enter")
            
            # Fill subject
            await fill_field_with_retry(page, "subject", email_data["subject"])
            
            # Fill body
            body_field = await wait_for_element(page, [
                "div[aria-label='Message Body']",
                "div[contenteditable='true']",
                "div[role='textbox']"
            ], 5000, "Message body")
            await body_field.click()
            await body_field.fill(str(email_data["body"]))
            
            # Send email
            send_btn = await wait_for_element(page, [
                'div[aria-label="Send ‪(Ctrl-Enter)‬"]',
                'div[data-tooltip="Send"]',
                'button[aria-label="Send"]',
                'div[role="button"]:has-text("Send")'
            ], 5000, "Send button")
            await send_btn.click()
            
            # Wait for confirmation
            await page.wait_for_selector("span.bAq", timeout=10000)
            logger.info("✅ Email sent successfully!")
            return True
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to send email after {max_retries} attempts: {e}")
                screenshot_path = await save_screenshot(page, f"send_error_attempt_{attempt + 1}")
                if screenshot_path:
                    logger.info(f"📸 Error screenshot saved: {screenshot_path}")
                raise
            else:
                logger.warning(f"Attempt {attempt + 1} failed, retrying: {e}")
                await asyncio.sleep(2)

# Async main function for standalone testing
async def main():
    """Async main function for testing the Gmail automation"""
    env = load_gmail_env()
    agent = GmailAgent(groq_api_key=env["GROQ_API_KEY"])
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="C:/Users/Sudharsan/AppData/Local/Google/Chrome/User Data/GmailAutomation",
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        
        page = await browser.new_page()
        await login(page, env)
        
        # Example usage
        email_data = {
            "to": ["test@example.com"],
            "subject": "Test Email from Async Gmail - Fixed",
            "body": "This is a test email sent using the improved async Playwright script!",
            "cc": [],
            "bcc": []
        }
        
        await send_email(page, email_data)
        await browser.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
