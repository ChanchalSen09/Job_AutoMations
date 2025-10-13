import requests
import time
import datetime
from bs4 import BeautifulSoup

# === CONFIGURATION ===
BOT_TOKEN = "8427330657:AAFPAWPFuUxd5rjf4vELuERRLWmfXUdfUUY"
CHAT_ID = "6010225944"

KEYWORDS = "Full Stack Developer React Node Django"
LOCATIONS = ["Indore", "Remote"]
REFRESH_INTERVAL = 2 * 60 * 60  
RESULT_LIMIT = 10 


def get_linkedin_jobs():
    jobs = []
    base_url = "https://www.linkedin.com/jobs/search/"
    for location in LOCATIONS:
        params = {
            "keywords": KEYWORDS,
            "location": location,
            "f_TPR": "r86400",  
            "sortBy": "DD",    
        }

        response = requests.get(base_url, params=params, headers={
            "User-Agent": "Mozilla/5.0"
        })

        soup = BeautifulSoup(response.text, "html.parser")
        listings = soup.find_all("a", class_="base-card__full-link", limit=RESULT_LIMIT)
        for link in listings:
            title = link.text.strip()
            url = link["href"].split("?")[0]
            jobs.append(f"💼 {title}\n📍 {location}\n🔗 {url}\n")
    return jobs


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=data)


def job_alert_loop():
    print("LinkedIn Job Alert Bot started!")
    while True:
        jobs = get_linkedin_jobs()
        if not jobs:
            send_telegram_message("No new jobs found in the last 2 hours.")
        else:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"Latest LinkedIn Openings ({now})\n\n" + "\n\n".join(jobs)
            send_telegram_message(message)
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    job_alert_loop()
