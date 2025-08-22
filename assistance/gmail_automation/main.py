from playwright.sync_api import sync_playwright
from gmail_automation.utils.env_loader import load_env
from gmail_automation.agents.gmail_agent import GmailAgent
from datetime import datetime
import json, os, time, sys

# -------- Utilities --------
def save_screenshot(page, label="after_action"):
    os.makedirs("screens", exist_ok=True)
    path = f"screens/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}.png"
    page.screenshot(path=path, full_page=True)
    return path


def login(page, env):
    page.goto("https://mail.google.com", wait_until="domcontentloaded")
    page.wait_for_selector("div[gh='cm']", timeout=120_000)
    page.wait_for_selector("div[role='main']", timeout=60_000)
    print("✅ Gmail session loaded via Chrome profile")


def preview_email(email_data):
    print("\n===== EMAIL PREVIEW =====")
    print("To:   ", ", ".join(email_data.get("to", [])))
    if email_data.get("cc"): print("Cc:   ", ", ".join(email_data["cc"]))
    if email_data.get("bcc"): print("Bcc:  ", ", ".join(email_data["bcc"]))
    print("Subject:", email_data["subject"])
    print("Body:\n" + email_data["body"])
    print("========================\n")


def parse_email_json(instructions: dict):
    # Expecting Python dict already from agent.parse_task
    required = ["subject", "body", "to", "cc", "bcc"]
    for k in required:
        if k not in instructions:
            raise ValueError(f"Missing field in instructions: {k}")
    # Ensure at least one recipient before sending; we'll ask the user if missing
    return instructions


def _type_recipients(page, field_name: str, emails: list):
    if not emails:
        return
    # Open Cc/Bcc panel if needed
    if field_name in ("cc", "bcc"):
        try:
            page.get_by_text("Cc Bcc", exact=False).click(timeout=2_000)
        except Exception:
            pass
    role_name = "To" if field_name == "to" else ("Cc" if field_name == "cc" else "Bcc")
    loc = page.get_by_role("textbox", name=role_name)
    try:
        loc.wait_for(state="visible", timeout=3_000)
    except Exception:
        # fallbacks
        candidates = [
            f"div[aria-label='{role_name}'] div[contenteditable='true']",
            f"div[role='textbox'][aria-label='{role_name}']",
            f"textarea[name='{field_name}']",
            f"input[aria-label='{role_name}']",
        ]
        for sel in candidates:
            l = page.locator(sel)
            try:
                l.wait_for(state="visible", timeout=1_000)
                loc = l
                break
            except Exception:
                continue
    loc.click()
    for addr in emails:
        page.keyboard.type(addr)
        page.keyboard.press("Enter")


def send_email(page, email_data):
    print("📩 Sending email:", {"to": email_data["to"], "subject": email_data["subject"]})
    try:
        page.click("div[gh='cm']", timeout=10_000)
        page.wait_for_selector("div[role='dialog']", timeout=15_000)

        # Robustly focus the To field: Gmail exposes it as a textbox with accessible name "To"
        # Prefer role-based selectors since accessible names are more stable than raw attributes.
        # Then fall back to common contenteditable/textbox patterns.
        to_locator = page.get_by_role("textbox", name="To")
        try:
            to_locator.wait_for(state="visible", timeout=7_000)
        except:
            # Fallbacks: chips container/editor Gmail uses during rollout changes
            candidates = [
                "div[aria-label='To'] div[contenteditable='true']",
                "div[aria-label='To']",
                "div[role='textbox'][aria-label='To']",
                "textarea[name='to']",
                "input[aria-label='To']",
            ]
            found = None
            for sel in candidates:
                loc = page.locator(sel)
                try:
                    loc.wait_for(state="visible", timeout=2_000)
                    found = loc
                    break
                except:
                    continue
            to_locator = found if found else to_locator

        # Ensure focus, then type the recipient
        to_locator.click()
        recipient = email_data["to"]
        if isinstance(recipient, list):
            recipient = ", ".join(recipient)
        page.keyboard.type(str(recipient))
        page.keyboard.press("Enter")  # create chip so subject becomes focusable

        # Subject: keep your selector, with a small wait as Gmail sometimes delays it
        page.wait_for_selector("input[name='subjectbox']", timeout=10_000)
        page.fill("input[name='subjectbox']", email_data["subject"])

        # Body: your existing logic with small resilience
        body = page.locator("div[aria-label='Message Body']").first
        if not body.count():
            body = page.locator("div[role='textbox'][aria-label]").first
        body.wait_for(state="visible", timeout=10_000)
        body.click()
        body.type(str(email_data["body"]), delay=5)

        # Send
        # Click by role/name (handles tooltip/aria-label variations)
        # If the above fails, fall back to visible text
        page.get_by_text("Send", exact=True).click(timeout=10_000)
        page.wait_for_selector("span.bAq", timeout=10_000)


        print("✅ Email sent!")
    except Exception as e:
        print(f"⚠️ Error sending email: {e}")
        raise


if __name__ == "__main__":
    env = load_env()
    agent = GmailAgent(groq_api_key=env["GROQ_API_KEY"]) 

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="C:/Users/Sudharsan/AppData/Local/Google/Chrome/User Data/GmailAutomation",
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        page = browser.new_page()
        login(page, env)

        print("\nGmail Assistant is ready. Examples:")
        print("  - 'Email my professor asking to extend the deadline to Friday; keep it formal.'")
        print("  - 'Send status update to team@acme.com; short, friendly tone.'")

        try:
            while True:
                task = input("\nYour command (type 'quit' to exit): ")
                if task.lower() in ["quit", "exit"]:
                    print("Exiting Gmail Assistant…")
                    break

                # Optional inline tone hint, e.g., '/tone=formal'
                tone_hint = None
                if "/tone=" in task:
                    try:
                        tone_hint = task.split("/tone=")[-1].split()[0]
                    except Exception:
                        pass

                try:
                    instructions = agent.parse_task(task, tone_hint=tone_hint)
                except Exception as e:
                    print("⚠️ LLM parse error:", e)
                    continue

                # Ensure at least one recipient; if none, ask now (interactive agent UX)
                if not instructions.get("to"):
                    to_addr = input("No recipient detected. Enter 'to' email (comma-separated for multiple): ").strip()
                    if to_addr:
                        instructions["to"] = [a.strip() for a in to_addr.split(",") if a.strip()]

                try:
                    email_data = parse_email_json(instructions)
                except Exception as e:
                    print("⚠️ Invalid instructions:", e)
                    continue

                preview_email(email_data)
                confirm = input("Send this email? [y/N] ").strip().lower()
                if confirm != "y":
                    # Allow quick edits
                    if input("Edit subject? [y/N] ").strip().lower() == "y":
                        email_data["subject"] = input("New subject: ")
                    if input("Edit body? [y/N] ").strip().lower() == "y":
                        print("Enter body. Finish with a single '.' on its own line:")
                        lines = []
                        while True:
                            line = sys.stdin.readline()
                            if line.strip() == ".":
                                break
                            lines.append(line.rstrip("\n"))
                        email_data["body"] = "\n".join(lines)
                    if input("Edit recipients? [y/N] ").strip().lower() == "y":
                        to_addr = input("To (comma-separated): ")
                        cc_addr = input("Cc (comma-separated): ")
                        bcc_addr = input("Bcc (comma-separated): ")
                        email_data["to"] = [a.strip() for a in to_addr.split(",") if a.strip()]
                        email_data["cc"] = [a.strip() for a in cc_addr.split(",") if a.strip()]
                        email_data["bcc"] = [a.strip() for a in bcc_addr.split(",") if a.strip()]

                try:
                    send_email(page, email_data)
                except Exception as e:
                    print("⚠️ Failed to send email:", e)
                path = save_screenshot(page, label="post_action")
                print(f"📸 Screenshot saved at: {path}")
        finally:
            try:
                browser.close()
            except Exception:
                pass
      