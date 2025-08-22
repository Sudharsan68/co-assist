import os
from datetime import datetime

def save_screenshot(page, folder="screenshots"):
    os.makedirs(folder, exist_ok=True)
    filename = datetime.now().strftime("%Y%m%d_%H%M%S.png")
    path = os.path.join(folder, filename)
    page.screenshot(path=path)
    return path
    