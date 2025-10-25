import requests
import time
import datetime
import asyncio
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest
from dotenv import load_dotenv
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import json

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# === CONFIGURATION ===
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Cron schedule: Run every 2 hours
CRON_SCHEDULE = "0 */2 * * *"

# File to store subscribed users
USERS_FILE = "subscribed_users.json"

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

EXPERIENCE_MATCH = [
    "0-1 years", "0-2 years", "0-3 years",
    "1-2 years", "1-3 years", "2-3 years",
    "fresher", "entry level", "entry-level",
    "junior", "associate", "graduate",
    "trainee", "intern", "recent graduate"
]

scheduler = None
subscribed_users = {}


def load_users():
    """Load subscribed users from file"""
    global subscribed_users
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                subscribed_users = json.load(f)
            logger.info(f"Loaded {len(subscribed_users)} subscribed users")
        else:
            subscribed_users = {}
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        subscribed_users = {}


def save_users():
    """Save subscribed users to file"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(subscribed_users, f, indent=2)
        logger.info(f"Saved {len(subscribed_users)} subscribed users")
    except Exception as e:
        logger.error(f"Error saving users: {e}")


def subscribe_user(chat_id, username=None, first_name=None):
    """Subscribe a user to job alerts"""
    chat_id_str = str(chat_id)
    subscribed_users[chat_id_str] = {
        "username": username,
        "first_name": first_name,
        "subscribed_at": datetime.datetime.now().isoformat(),
        "active": True
    }
    save_users()
    logger.info(f"User {chat_id} ({username or first_name}) subscribed")


def unsubscribe_user(chat_id):
    """Unsubscribe a user from job alerts"""
    chat_id_str = str(chat_id)
    if chat_id_str in subscribed_users:
        subscribed_users[chat_id_str]["active"] = False
        save_users()
        logger.info(f"User {chat_id} unsubscribed")


def is_subscribed(chat_id):
    """Check if user is subscribed"""
    chat_id_str = str(chat_id)
    return chat_id_str in subscribed_users and subscribed_users[chat_id_str].get("active", False)


def get_active_users():
    """Get list of active subscribed users"""
    return [int(uid) for uid, data in subscribed_users.items() if data.get("active", False)]


def get_linkedin_jobs():
    """Scrape LinkedIn jobs"""
    jobs = []
    job_urls = set()
    base_url = "https://www.linkedin.com/jobs/search/"
    
    logger.info("Starting job search...")
    
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
                "f_TPR": "r86400",
                "sortBy": "DD",
                "f_E": "1,2,3",
            }

            try:
                response = requests.get(base_url, params=params, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                }, timeout=15)

                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                listings = (
                    soup.find_all("div", class_="base-card") or
                    soup.find_all("div", class_="job-search-card") or
                    soup.find_all("li") or
                    soup.find_all("div", class_="base-search-card")
                )

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
                        location_elem = listing.find("span", class_="job-search-card__location")
                        time_elem = listing.find("time")

                        if not title_elem or not link_elem:
                            continue

                        title = title_elem.text.strip()
                        url = link_elem.get("href", "").split("?")[0]
                        if not url or url in job_urls:
                            continue

                        if time_elem and time_elem.text:
                            posted_text = time_elem.text.strip().lower()
                            if "hour" in posted_text:
                                try:
                                    hours = int(''.join([c for c in posted_text if c.isdigit()]) or "0")
                                    if hours < 1 or hours > 24:
                                        continue
                                except:
                                    continue
                            elif "day" in posted_text:
                                if not posted_text.startswith("1 day"):
                                    continue
                            else:
                                continue
                        else:
                            continue

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
                            f"🕐 {posted_time}\n"
                            f"🔗 {url}"
                        )

                        category_jobs.append(job_info)
                        job_urls.add(url)
                        total_found += 1

                    except Exception:
                        continue

            except Exception as e:
                logger.error(f"Error searching {keyword} in {location}: {e}")

            time.sleep(2)

        jobs.extend(category_jobs[:per_category_limit])

        if total_found >= total_limit:
            break

    logger.info(f"Found {len(jobs)} jobs")
    return jobs


async def send_job_alert_to_user(context, chat_id):
    """Send job alerts to a specific user"""
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
            f"🕐 {now}\n"
            f"✅ Found {len(jobs)} relevant positions\n\n"
            + "\n\n".join(jobs)
        )
    
    try:
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
        return True
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")
        return False


async def scheduled_job_alert(app):
    """Scheduled job that runs via cron - sends to ALL subscribed users"""
    logger.info(f"🔔 Running scheduled job alert at {datetime.datetime.now()}")
    
    active_users = get_active_users()
    logger.info(f"Sending alerts to {len(active_users)} subscribed users")
    
    # Get jobs once
    jobs = get_linkedin_jobs()
    
    if not jobs:
        message = (
            "🔍 <b>No matching jobs found</b>\n\n"
            "No new jobs matching your profile in the last search."
        )
    else:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"📢 <b>Jobs Matching Your Profile</b>\n"
            f"🕐 {now}\n"
            f"✅ Found {len(jobs)} relevant positions\n\n"
            + "\n\n".join(jobs)
        )
    
    # Send to all subscribed users
    success_count = 0
    for chat_id in active_users:
        try:
            await app.bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.1)  # Small delay to avoid rate limits
        except Exception as e:
            logger.error(f"Failed to send to {chat_id}: {e}")
    
    logger.info(f"Sent alerts to {success_count}/{len(active_users)} users")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Auto-subscribe user when they start
    subscribe_user(chat_id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("🔍 Get Jobs Now", callback_data="get_jobs")],
        [InlineKeyboardButton("🔔 Subscribe", callback_data="subscribe"),
         InlineKeyboardButton("🔕 Unsubscribe", callback_data="unsubscribe")],
        [InlineKeyboardButton("⏰ Cron Status", callback_data="cron_status")],
        [InlineKeyboardButton("ℹ️ Status", callback_data="status")],
        [InlineKeyboardButton("👤 Profile Match", callback_data="profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"👋 <b>Welcome {user.first_name}!</b>\n\n"
        "🎯 <b>Job Search Profile:</b>\n"
        "• Full Stack | Frontend | Backend Developer\n"
        "• React | Node.js | Python | Django\n"
        "• Experience: 0-3 years (Fresher to Mid-level)\n"
        "• Locations: Indore, Remote, India\n"
        f"• 🔔 <b>Auto alerts: Every 2 hours</b>\n\n"
        "✅ <b>You are now subscribed!</b>\n"
        "You'll receive job alerts every 2 hours automatically.\n\n"
        "Use the buttons below:"
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode="HTML")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    chat_id = query.message.chat_id
    user = query.from_user
    
    try:
        await query.answer()
    except BadRequest as e:
        if "query is too old" not in str(e).lower():
            raise
    
    try:
        if query.data == "subscribe":
            subscribe_user(chat_id, user.username, user.first_name)
            await query.edit_message_text(
                "✅ <b>Subscribed!</b>\n\n"
                "You'll receive job alerts every 2 hours automatically.\n"
                "Use /start to see controls.",
                parse_mode="HTML"
            )
        
        elif query.data == "unsubscribe":
            unsubscribe_user(chat_id)
            await query.edit_message_text(
                "🔕 <b>Unsubscribed!</b>\n\n"
                "You won't receive automatic alerts anymore.\n"
                "You can still use '🔍 Get Jobs Now' manually.\n"
                "Use /start to subscribe again.",
                parse_mode="HTML"
            )
        
        elif query.data == "status":
            sub_status = "🟢 Subscribed" if is_subscribed(chat_id) else "🔴 Not Subscribed"
            total_users = len(get_active_users())
            status_text = (
                f"📊 <b>Your Status</b>\n\n"
                f"Subscription: {sub_status}\n"
                f"Total active users: {total_users}\n"
                f"Schedule: Every 2 hours (Cron Job)\n"
                f"Next runs: 00:00, 02:00, 04:00, etc.\n\n"
                f"Use /start to manage subscription.",
            )
            await query.edit_message_text(status_text, parse_mode="HTML")
        
        elif query.data == "get_jobs":
            await query.edit_message_text("🔍 Searching for jobs matching your profile...")
            await send_job_alert_to_user(context, chat_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Search complete! Use /start to see controls.",
                parse_mode="HTML"
            )
        
        elif query.data == "cron_status":
            total_users = len(get_active_users())
            cron_text = (
                f"⏰ <b>Cron Job Status</b>\n\n"
                f"Status: 🟢 Active\n"
                f"Schedule: {CRON_SCHEDULE}\n"
                f"Frequency: Every 2 hours\n"
                f"Subscribed users: {total_users}\n"
                f"Timezone: UTC\n\n"
                f"All subscribed users receive alerts automatically."
            )
            await query.edit_message_text(cron_text, parse_mode="HTML")
        
        elif query.data == "profile":
            profile_text = (
                "👤 <b>Job Match Criteria:</b>\n\n"
                "<b>🎯 Target Roles:</b>\n"
                "Full Stack, Frontend, Backend Developer\n\n"
                "<b>✅ Required Skills:</b>\n"
                "React.js, Node.js, JavaScript, Python, Django\n\n"
                "<b>⭐ Preferred Skills:</b>\n"
                "Redux, Tailwind, Express, MongoDB, SQL, Next.js\n\n"
                "<b>🎯 Experience Level:</b>\n"
                "0-3 years, Fresher, Entry Level, Junior\n\n"
                "<b>❌ Excluded:</b>\n"
                "Senior, Lead, 4+ years experience\n\n"
                "<b>📍 Locations:</b>\n"
                "Indore, Remote, India"
            )
            await query.edit_message_text(profile_text, parse_mode="HTML")
    
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        elif "query is too old" in str(e).lower():
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Button expired. Please use /start to get a fresh menu.",
                parse_mode="HTML"
            )
        else:
            logger.error(f"BadRequest error: {e}")
    except Exception as e:
        logger.error(f"Error in button handler: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 <b>Bot Commands:</b>\n\n"
        "/start - Subscribe & show controls\n"
        "/help - Show this help\n"
        "/status - Check your status\n\n"
        "<b>Features:</b>\n"
        "• Auto job alerts every 2 hours\n"
        "• Smart filtering for your skills\n"
        "• Multi-user support\n"
        "• Manual job search anytime\n"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    chat_id = update.effective_chat.id
    sub_status = "🟢 Subscribed" if is_subscribed(chat_id) else "🔴 Not Subscribed"
    total_users = len(get_active_users())
    
    status_text = (
        f"📊 <b>Your Status</b>\n\n"
        f"Subscription: {sub_status}\n"
        f"Total users: {total_users}\n"
        f"Schedule: Every 2 hours\n\n"
        f"Use /start to manage subscription."
    )
    await update.message.reply_text(status_text, parse_mode="HTML")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot"""
    global scheduler
    
    logger.info("🤖 LinkedIn Job Alert Bot - Multi-user Edition")
    logger.info("✅ Full Stack | Frontend | Backend roles")
    logger.info("📊 Experience: 0-3 years")
    logger.info(f"⏰ Cron: {CRON_SCHEDULE}")
    
    # Load existing users
    load_users()
    logger.info(f"Loaded {len(get_active_users())} active users")
    
    # Create app
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    # Setup scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_job_alert,
        trigger=CronTrigger.from_crontab(CRON_SCHEDULE),
        args=[app],
        id='job_alert',
        name='LinkedIn Job Alert',
        replace_existing=True
    )
    scheduler.start()
    
    logger.info(f"✅ Cron scheduled: {CRON_SCHEDULE}")
    logger.info("✅ Bot ready! Always-on mode.")
    
    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()