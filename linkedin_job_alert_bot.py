import requests
import time
import datetime
import threading
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
load_dotenv()

# === CONFIGURATION ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 8000))

# Updated keywords based on your resume - search for multiple role types
SEARCH_KEYWORDS = [
    "Full Stack Developer",
    "Frontend Developer", 
    "Backend Developer",
    "React Developer",
    "Node.js Developer",
    "Python Developer",
    "JavaScript Developer",
    "Software Developer",
    "Web Developer"
]

LOCATIONS = ["Indore", "Remote", "India"]
REFRESH_INTERVAL = 2 * 60 * 60  # 2 hours
RESULT_LIMIT = 15  # Per keyword search

# Profile matching criteria based on your resume
REQUIRED_SKILLS = [
    "react", "reactjs", "react.js",
    "node", "nodejs", "node.js",
    "javascript", "typescript", "js",
    "frontend", "backend", "full stack", "fullstack",
    "django", "python", "web developer", "software developer"
]

PREFERRED_SKILLS = [
    "redux", "tailwind", "tailwindcss",
    "express", "expressjs", "mongodb", "sql",
    "rest api", "api", "next.js", "nextjs",
    "html", "css", "git", "aws"
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "architect",
    "4+ years", "5+ years", "5 years", "6+ years", "7+ years", "8+ years",
    "manager", "head of", "director", "vp", "chief",
    "staff engineer", "distinguished"
]

# Experience level keywords to look for (0-3 years)
EXPERIENCE_MATCH = [
    "0-1 years", "0-2 years", "0-3 years",
    "1-2 years", "1-3 years", "2-3 years",
    "fresher", "entry level", "entry-level",
    "junior", "associate", "graduate",
    "trainee", "intern", "recent graduate"
]


def job_matches_profile(title, description=""):
    """Check if job matches your profile"""
    text = (title + " " + description).lower()
    
    # Exclude senior/lead positions and high experience requirements
    for exclude in EXCLUDE_KEYWORDS:
        if exclude.lower() in text:
            return False
    
    # Must have at least one required skill
    has_required = any(skill in text for skill in REQUIRED_SKILLS)
    
    if not has_required:
        return False
    
    preferred_count = sum(1 for skill in PREFERRED_SKILLS if skill in text)
    
    # Check for experience match
    has_exp_match = any(exp in text for exp in EXPERIENCE_MATCH)
    
    return has_required


def get_linkedin_jobs():
    """Scrape LinkedIn jobs (posted in the last 1-24 hours, 2 per category, max 20 total)"""
    jobs = []
    job_urls = set()
    base_url = "https://www.linkedin.com/jobs/search/"
    
    print(f"\n🔍 Starting latest job search (posted within last 1-24 hours, 2 per category)...")
    
    total_limit = 20
    per_category_limit = 2
    total_found = 0

    for keyword in SEARCH_KEYWORDS:
        category_jobs = []

        for location in LOCATIONS:
            if total_found >= total_limit:
                break

            params = {
                "keywords": keyword,
                "location": location,
                "f_TPR": "r86400",  # Posted in last 24 hours
                "sortBy": "DD",     # Date posted (latest first)
                "f_E": "1,2,3",     # Entry level, Associate, Internship
            }

            try:
                print(f"   Searching: {keyword} in {location}...")
                response = requests.get(base_url, params=params, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                }, timeout=15)

                if response.status_code != 200:
                    print(f"   ⚠️ HTTP {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                listings = (
                    soup.find_all("div", class_="base-card") or
                    soup.find_all("div", class_="job-search-card") or
                    soup.find_all("li") or
                    soup.find_all("div", class_="base-search-card")
                )

                count = 0
                for listing in listings:
                    if len(category_jobs) >= per_category_limit or total_found >= total_limit:
                        break

                    try:
                        title_elem = (
                            listing.find("h3", class_="base-search-card__title") or
                            listing.find("h3") or
                            listing.find("a", class_="base-card__full-link")
                        )
                        link_elem = (
                            listing.find("a", class_="base-card__full-link") or
                            listing.find("a", href=True)
                        )
                        company_elem = (
                            listing.find("h4", class_="base-search-card__subtitle") or
                            listing.find("span", class_="job-search-card__subtitle")
                        )
                        location_elem = (
                            listing.find("span", class_="job-search-card__location")
                        )
                        time_elem = listing.find("time")

                        if not title_elem or not link_elem:
                            continue

                        title = title_elem.text.strip()
                        url = link_elem.get("href", "").split("?")[0]
                        if not url or url in job_urls:
                            continue

                        # ⏰ Filter by posted time (1-24 hours)
                        if time_elem and time_elem.text:
                            posted_text = time_elem.text.strip().lower()
                            # Example values: "1 hour ago", "3 hours ago", "1 day ago"
                            if "hour" in posted_text:
                                try:
                                    hours = int(''.join([c for c in posted_text if c.isdigit()]) or "0")
                                    if hours < 1 or hours > 24:
                                        continue
                                except:
                                    continue
                            elif "day" in posted_text:
                                # Accept if exactly 1 day (≈ 24 hours) but skip if more than 1 day
                                if not posted_text.startswith("1 day"):
                                    continue
                            else:
                                continue  # skip if “weeks ago” or older
                        else:
                            continue  # no timestamp found, skip

                        title_lower = title.lower()
                        if not any(skill in title_lower for skill in REQUIRED_SKILLS):
                            continue
                        if any(exclude in title_lower for exclude in EXCLUDE_KEYWORDS):
                            continue

                        company = company_elem.text.strip() if company_elem else "Company"
                        job_location = location_elem.text.strip() if location_elem else location
                        posted_time = time_elem.text.strip() if time_elem else "Recently"

                        job_info = (
                            f"💼 <b>{title}</b>\n"
                            f"🏢 {company}\n"
                            f"📍 {job_location}\n"
                            f"🕒 {posted_time}\n"
                            f"🔗 {url}"
                        )

                        category_jobs.append(job_info)
                        job_urls.add(url)
                        total_found += 1
                        count += 1

                    except Exception:
                        continue

                print(f"   ✅ Found {count} recent jobs for {keyword} in {location}")

            except Exception as e:
                print(f"   ❌ Error: {e}")

            time.sleep(2)

        jobs.extend(category_jobs[:per_category_limit])

        if total_found >= total_limit:
            break

    print(f"\n📊 Total latest jobs found: {len(jobs)} (posted in last 1-24 hours, max 20 total)")
    return jobs

def send_telegram_message_sync(message):
    """Send message using synchronous requests"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Split message if too long
    if len(message) > 4000:
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for chunk in chunks:
            data = {"chat_id": CHAT_ID, "text": chunk, "parse_mode": "HTML"}
            requests.post(url, data=data)
    else:
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data)


async def send_job_alert(context):
    """Send job alerts to the user"""
    jobs = get_linkedin_jobs()
    
    if not jobs:
        message = (
            "🔍 <b>No matching jobs found</b>\n\n"
            "No new jobs matching your profile in the last search.\n"
            "The bot is filtering for:\n"
            "• Developer roles: Full Stack, Frontend, Backend\n"
            "• Tech: React, Node.js, Python, Django, JavaScript\n"
            "• Experience: 0-3 years (including Freshers)\n"
            "• Entry-level to Mid-level positions"
        )
    else:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"📢 <b>Jobs Matching Your Profile</b>\n"
            f"🕒 {now}\n"
            f"✅ Found {len(jobs)} relevant positions\n\n"
            + "\n\n".join(jobs)
        )
    
    try:
        await context.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending message: {e}")


# Bot state
bot_running = False
job_thread = None


def job_alert_loop():
    """Background thread to send periodic job alerts"""
    global bot_running
    
    while bot_running:
        try:
            jobs = get_linkedin_jobs()
            
            if not jobs:
                message = (
                    "🔍 <b>No matching jobs found</b>\n\n"
                    "No new jobs matching your profile in the last search.\n"
                    "The bot is filtering for:\n"
                    "• Developer roles: Full Stack, Frontend, Backend\n"
                    "• Tech: React, Node.js, Python, Django, JavaScript\n"
                    "• Experience: 0-3 years (including Freshers)\n"
                    "• Entry-level to Mid-level positions"
                )
            else:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = (
                    f"📢 <b>Jobs Matching Your Profile</b>\n"
                    f"🕒 {now}\n"
                    f"✅ Found {len(jobs)} relevant positions\n\n"
                    + "\n\n".join(jobs)
                )
            
            send_telegram_message_sync(message)
            
        except Exception as e:
            print(f"Error in job alert loop: {e}")
        
        # Sleep for the refresh interval
        for _ in range(REFRESH_INTERVAL):
            if not bot_running:
                break
            time.sleep(1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    keyboard = [
        [InlineKeyboardButton("▶️ Start Alerts", callback_data="start_alerts")],
        [InlineKeyboardButton("⏸️ Stop Alerts", callback_data="stop_alerts")],
        [InlineKeyboardButton("🔍 Get Jobs Now", callback_data="get_jobs")],
        [InlineKeyboardButton("ℹ️ Status", callback_data="status")],
        [InlineKeyboardButton("👤 Profile Match", callback_data="profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        "👋 <b>Welcome Chanchal!</b>\n\n"
        "🎯 <b>Job Search Profile:</b>\n"
        "• Full Stack | Frontend | Backend Developer\n"
        "• React | Node.js | Python | Django\n"
        "• Experience: 0-3 years (Fresher to Mid-level)\n"
        "• Locations: Indore, Remote, India\n"
        f"• Auto-refresh: Every {REFRESH_INTERVAL // 3600} hours\n\n"
        "✅ <b>Searching for roles:</b>\n"
        "• Full Stack Developer\n"
        "• Frontend Developer (React)\n"
        "• Backend Developer (Node/Python)\n"
        "• JavaScript/TypeScript Developer\n"
        "• Web Developer\n"
        "• Software Developer\n\n"
        "✅ <b>Tech Stack Match:</b>\n"
        "React, Node.js, Django, Python, JavaScript, TypeScript, Express, MongoDB, SQL\n\n"
        "❌ <b>Excluding:</b>\n"
        "• Senior/Lead/Architect roles\n"
        "• 4+ years experience required\n\n"
        "Use the buttons below to control:"
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode="HTML")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    global bot_running, job_thread
    
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_alerts":
        if bot_running:
            await query.edit_message_text("✅ Job alerts are already running!")
        else:
            bot_running = True
            job_thread = threading.Thread(target=job_alert_loop, daemon=True)
            job_thread.start()
            await query.edit_message_text(
                f"✅ <b>Job alerts started!</b>\n\n"
                f"You'll receive filtered jobs every {REFRESH_INTERVAL // 3600} hours.\n"
                f"Searching for: Full Stack, Frontend, Backend, React, Node.js, Python roles.\n"
                f"Experience: 0-3 years (Fresher to Mid-level)\n\n"
                f"Use /start to see controls again.",
                parse_mode="HTML"
            )
    
    elif query.data == "stop_alerts":
        if not bot_running:
            await query.edit_message_text("⏸️ Job alerts are already stopped!")
        else:
            bot_running = False
            if job_thread:
                job_thread.join(timeout=2)
            await query.edit_message_text(
                "⏸️ <b>Job alerts stopped!</b>\n\nUse /start to restart alerts.",
                parse_mode="HTML"
            )
    
    elif query.data == "status":
        status = "🟢 Running" if bot_running else "🔴 Stopped"
        await query.edit_message_text(
            f"📊 <b>Bot Status</b>\n\n"
            f"Status: {status}\n"
            f"Target Role: Full Stack Developer\n"
            f"Experience: 1-3 years\n"
            f"Locations: {', '.join(LOCATIONS)}\n"
            f"Interval: {REFRESH_INTERVAL // 3600} hours\n\n"
            f"Use /start to see controls.",
            parse_mode="HTML"
        )
    
    elif query.data == "get_jobs":
        await query.edit_message_text("🔍 Searching for jobs matching your profile...")
        await send_job_alert(context)
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="✅ Search complete! Use /start to see controls.",
            parse_mode="HTML"
        )
    
    elif query.data == "profile":
        profile_text = (
            "👤 <b>Your Profile Match Criteria:</b>\n\n"
            "<b>🎯 Target Roles:</b>\n"
            "• Full Stack Developer\n"
            "• Frontend Developer (React)\n"
            "• Backend Developer (Node.js/Python)\n"
            "• JavaScript/TypeScript Developer\n"
            "• Python/Django Developer\n"
            "• Web Developer\n"
            "• Software Developer\n\n"
            "<b>✅ Required Skills (Any):</b>\n"
            "React.js, Node.js, JavaScript, TypeScript, Python, Django, Frontend, Backend, Full Stack\n\n"
            "<b>⭐ Preferred Skills:</b>\n"
            "Redux, Tailwind CSS, Express.js, MongoDB, SQL, REST API, Next.js, HTML, CSS, Git, AWS\n\n"
            "<b>🎯 Experience Level:</b>\n"
            "0-3 years, Fresher, Entry Level, Junior, Associate, Trainee\n\n"
            "<b>❌ Excluded:</b>\n"
            "Senior, Lead, Principal, Architect, Manager, 4+ years experience\n\n"
            "<b>📍 Locations:</b>\n"
            "Indore, Remote, India"
        )
        await query.edit_message_text(profile_text, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 <b>Bot Commands:</b>\n\n"
        "/start - Show control panel\n"
        "/help - Show this help message\n"
        "/status - Check bot status\n\n"
        "<b>Features:</b>\n"
        "• Smart filtering based on your resume\n"
        "• Auto-excludes senior positions\n"
        "• Matches React, Node.js, Django roles\n"
        "• Start/Stop automatic alerts\n"
        "• Get jobs on demand\n"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    status = "🟢 Running" if bot_running else "🔴 Stopped"
    status_text = (
        f"📊 <b>Bot Status</b>\n\n"
        f"Status: {status}\n"
        f"Roles: Full Stack, Frontend, Backend, React, Node, Python\n"
        f"Experience: 0-3 years\n"
        f"Locations: {', '.join(LOCATIONS)}\n"
        f"Interval: {REFRESH_INTERVAL // 3600} hours"
    )
    await update.message.reply_text(status_text, parse_mode="HTML")

# Simple HTTP server for health checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def run_http_server():
    """Run simple HTTP server for Render health checks"""
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    print(f"✅ HTTP server running on port {PORT}")
    server.serve_forever()



def main():
    """Start the bot"""
    print("🤖 LinkedIn Job Alert Bot for Chanchal Sen")
    print("🎯 Searching for multiple developer roles")
    print("✅ Full Stack | Frontend | Backend | React | Node.js | Python")
    print("📊 Experience: 0-3 years (Fresher to Mid-level)")
    print("📍 Indore, Remote, India")
    
    # Create the Application
    app = Application.builder().token(BOT_TOKEN).build()
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()  
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Start the bot
    print("\n✅ Bot is ready! Send /start to begin.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()