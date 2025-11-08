import copy
import csv
import json
import logging
import os
import random
import re
import sqlite3
import subprocess
import time
import zipfile
from PIL import Image
import tempfile
import pdf2image
import PyPDF2
import google.generativeai as genai
import docx
from pathlib import Path
import telebot
import yt_dlp
from dotenv import load_dotenv
from telebot import types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommandScopeChat

load_dotenv()

# ------------------------------------------------------------------------------
# App / Bot setup
# ------------------------------------------------------------------------------
TOKEN = os.getenv("TELEGRAM_BOT_API")
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
bot = telebot.TeleBot(TOKEN)

ADMIN_CHAT_ID = None
AMAR_CHAT_ID = None
AWAB_CHAT_ID = None

SUBSCRIBERS_FILE = "subscribers.json"
SUBJECTS_JSON = "semester_subjects.json"
FLASHCARDS_FILE = "flashcards.json"
SUBJECT_FILE = "subject_channels.json"
SETTINGS_FILE = "user_settings.json"
BLOCKED_FILE = "blocked_users.json"
RESPONSES_FILE = "response.json"
USER_FULL_DATA = "user_full_data.json"
current_version = "3.0.0"
start_time = time.time()

# runtime state
user_state = {}
user_states = {}
user_sessions = {}
user_video_urls = {}
user_format_ids = {}
user_quiz_state = {}
user_data = {}  # used by /img_pdf flow

json_files = [
    "subscribers.json",
    "semester_subjects.json",
    "flashcards.json",
    "subject_channels.json",
    "user_settings.json",
]

department_codes = {
    "3030": "electronics",
     "4040": "mechatronics",
    "5050": "biomedical",
    "6060": "computer",
     "7070": "t.com",
     "8080": "linux"
}

GROUP_IDS = {
    "electronics": -1002601636422,
     "mechatronics": -4989575463,
    "biomedical": -4896388043,
    "computer": -4916986833,
     "tcom": -4973193836,
     "linux":-4822189190
}

HELP = (
    "This is a study bot which can do this commands :\n"
    "/start - Restart the bot\n"
    "/cancel - Cancel the function\n"
    "/subscribe - subscribe to broadcasts\n"
    "/unsubscribe - unsubscribe to broadcasts\n"
    "/lecture - Download selected subject PDFs\n"
    "/lecture_video - Access lecture video via channels\n"
    "/img_pdf - Convert images to PDFs\n"
    "/pdf_img - Convert PDFs to images\n"
    "/create_subject - allow you to create specific subject path for flashcards\n"
    "/delete_subject - allow you to delete specific subject path\n"
    "/add_flashcard - Add study flashcards and get quizzed\n"
    "/view_flashcards - Allow you to view saved flashcards\n"
    "/delete_flashcard - Delete a specific flashcard\n"
    "/start_quiz - Quiz you randomly from flashcards (now supports MCQ 🎯)\n"
    "/report - Report issues\n"
    "/ai - Study Bot Ai"

)

# Normal user commands
user_commands = [
    types.BotCommand("start", "Restart the bot"),
    types.BotCommand("cancel", "Cancel the function"),
    types.BotCommand("help", "Help me!"),
    types.BotCommand("about_me", "About me"),
    types.BotCommand("donate", "Help the bot"),
    types.BotCommand("subscribe", "Subscribe to broadcasts"),
    types.BotCommand("unsubscribe", "Unsubscribe from broadcasts"),
    types.BotCommand("choose_settings", "Set your preferred settings"),
    types.BotCommand("lecture", "Download selected subject PDFs"),
    types.BotCommand("youtube", "Download YouTube videos"),
    types.BotCommand("img_pdf", "Convert images to PDFs"),
    types.BotCommand("pdf_img", "Convert PDFs to images"),
    types.BotCommand("create_subject", "Create a subject path for flashcards"),
    types.BotCommand("delete_subject", "Delete a subject path"),
    types.BotCommand("add_flashcard", "Add study flashcards and get quizzed"),
    types.BotCommand("view_flashcards", "View saved flashcards"),
    types.BotCommand("delete_flashcard", "Delete a specific flashcard"),
    types.BotCommand("import_flashcards", "Import flashcards as CSV"),
    types.BotCommand("export_flashcards", "Export flashcards as CSV"),
    types.BotCommand("start_quiz", "Quiz you randomly from flashcards"),
    types.BotCommand("report", "Report issues"),
    types.BotCommand("my_id", "Your Telegram ID"),
    types.BotCommand("ai", "Your Study Bot Ai")
]

# Admin commands
admin_commands = [
    types.BotCommand("send_message", "ADMIN"),
    types.BotCommand("send_admins", "ADMIN"),
    types.BotCommand("upload", "ADMIN"),
    types.BotCommand("upload_video", "ADMIN"),
    types.BotCommand("broadcast", "ADMIN"),
    types.BotCommand("nofs", "ADMIN"),
    types.BotCommand("count", "ADMIN"),
    types.BotCommand("up_time", "ADMIN"),
    types.BotCommand("copy_subject", "ADMIN"),
    types.BotCommand("delete_subject_path", "ADMIN"),
    types.BotCommand("dashboard", "ADMIN")
]

# Set global commands for all users
bot.set_my_commands(user_commands)
for admin in ADMIN_CHAT_ID:
    try:
        bot.set_my_commands(user_commands + admin_commands, scope=BotCommandScopeChat(chat_id=admin))
    except Exception as e:
        print(e)


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(
    filename="study_bot_log.log",
    filemode="w",
    level=logging.DEBUG,
    encoding="utf-8",
    format="%(asctime)s - %(levelname)s: [%(filename)s - line:%(lineno)d] %(message)s",
    datefmt="%d/%m/%Y %I:%M:%S %p",
)
logger = logging.getLogger(__name__)
print("Bot Started or restarted")
logger.info("Bot Started")

# ------------------------------------------------------------------------------
# Data loading (tolerant if files are missing)
# ------------------------------------------------------------------------------
def load_json_or_default(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


flashcards_data = load_json_or_default(FLASHCARDS_FILE, {})
semester_grouped_subjects = load_json_or_default(SUBJECTS_JSON, {})
subject_channels = load_json_or_default(SUBJECT_FILE, {})
user_settings = load_json_or_default(SETTINGS_FILE, {})
blocked_users = load_json_or_default(BLOCKED_FILE, [])
_subs_list = load_json_or_default(SUBSCRIBERS_FILE, [])
user_data_load = load_json_or_default(USER_FULL_DATA, {})
subscribers = set(_subs_list)  # keep as set internally






# ------------------------------------------------------------------------------
# Misc mappings & helpers
# ------------------------------------------------------------------------------


def department_buttons(prefix):
    markup = types.InlineKeyboardMarkup()
    for code, name in department_codes.items():
        markup.add(types.InlineKeyboardButton(f"{code} - {name.title()}", callback_data=f"{prefix}_{name}"))
    return markup

# ------------------------------------------------------------------------------
# Git helper (Render-safe)
# ------------------------------------------------------------------------------
subprocess.run(["git", "config", "user.name", "Awab Azhari"])
subprocess.run(["git", "config", "user.email", "awab.azharii@gmail.com"])

def git_is_shallow_repo() -> bool:
    # repo is shallow if .git/shallow exists
    try:
        git_dir = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, text=True, check=True).stdout.strip()
        return os.path.exists(os.path.join(git_dir, "shallow"))
    except Exception:
        return False

def git_commit_and_push(files=None, commit_message="Update JSON data", allow_force=True):

    def run(cmd, check=True, capture=False):
        if capture:
            return subprocess.run(cmd, check=check, text=True, capture_output=True)
        return subprocess.run(cmd, check=check)

    def safe_run(cmd):
        try:
            run(cmd)
        except subprocess.CalledProcessError:
            pass

    try:
        username = "mrawab"
        repo = "Study-Bot-Render"
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is not set")

        push_url = f"https://{username}:{token}@github.com/{username}/{repo}.git"

        # Ensure git identity
        safe_run(["git", "config", "user.name", "Awab Azhari"])
        safe_run(["git", "config", "user.email", "awab.azharii@gmail.com"])

        # Make sure we are inside a git repo
        try:
            out = run(["git", "rev-parse", "--is-inside-work-tree"], capture=True)
            if out.stdout.strip() != "true":
                raise RuntimeError("Not inside a git work tree")
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Not inside a git repository") from e

        # Point origin to token URL
        try:
            run(["git", "remote", "set-url", "origin", push_url])
        except subprocess.CalledProcessError:
            run(["git", "remote", "add", "origin", push_url])

        # Abort any in-progress operations that block us
        # (your logs show rebase conflicts lingering)
        safe_run(["git", "rebase", "--abort"])
        safe_run(["git", "merge", "--abort"])
        # Reset staged conflicts if any
        safe_run(["git", "reset", "--merge"])
        # Also clear incomplete cherry-picks/reverts
        safe_run(["git", "cherry-pick", "--abort"])
        safe_run(["git", "revert", "--abort"])

        # Find current branch; fix detached HEAD by creating/switching to main
        head = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True).stdout.strip()

        # Always fetch before checkout logic
        safe_run(["git", "fetch", "origin", "--prune", "--tags"])

        if head == "HEAD":
            # Detached: try to base main on origin/main if it exists
            # If origin/main missing (first push), we'll just create an empty main
            try:
                run(["git", "checkout", "-B", "main", "origin/main"])
            except subprocess.CalledProcessError:
                run(["git", "checkout", "-B", "main"])
        else:
            # Stay on current branch; if it's not main, you can either keep it,
            # or normalize everything onto main. We'll normalize onto main:
            if head != "main":
                # If origin/main exists, base on it
                try:
                    run(["git", "checkout", "-B", "main", "origin/main"])
                except subprocess.CalledProcessError:
                    run(["git", "checkout", "-B", "main"])

        # Stage changes (parameter 'files' kept for compatibility, but we add all)
        run(["git", "add", "-A"])

        # Commit only if there are changes
        status = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
        if status:
            run(["git", "commit", "-m", commit_message])
        else:
            print("ℹ️ No changes to commit.")

        # Ensure full history if shallow clone (ignore error if already full)
        safe_run(["git", "fetch", "--unshallow"])
        safe_run(["git", "fetch", "origin", "--prune", "--tags"])

        # 1) Try rebase-based pull first (linear history)
        try:
            run(["git", "pull", "--rebase", "origin", "main"])
        except subprocess.CalledProcessError:
            # Abort rebase and try a merge preferring local JSON updates
            safe_run(["git", "rebase", "--abort"])
            # If there are local commits, merge remote preferring ours
            try:
                run(["git", "pull", "--no-rebase", "-X", "ours", "--no-edit", "origin", "main"])
            except subprocess.CalledProcessError:
                # As a final fallback, reset to remote, re-apply staged changes if any,
                # or just push with force-with-lease if allowed.
                # Hard reset might discard local uncommitted (we already committed above).
                safe_run(["git", "reset", "--hard", "origin/main"])

        # 2) Push
        try:
            run(["git", "push", "origin", "HEAD:main"])
        except subprocess.CalledProcessError as e:
            if allow_force:
                # Safe force (refuses if remote advanced after our fetch)
                run(["git", "push", "--force-with-lease", "origin", "HEAD:main"])
            else:
                raise

        print("✅ Successfully pushed JSON updates to GitHub.")
        try:
            bot.send_message(AWAB_CHAT_ID, "Updated Json Files")
        except Exception:
            pass

    except Exception as e:
        print(f"❌ Git push failed: {e}")
        try:
            bot.send_message(AWAB_CHAT_ID, f"Git push failed: {e}")
        except Exception:
            pass



# ------------------------------------------------------------------------------
# Save helpers (use globals consistently)
# ------------------------------------------------------------------------------
def save_flashcards(flashcards):
    with open(FLASHCARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(flashcards, f, indent=4, ensure_ascii=False)
    git_commit_and_push(json_files, "Auto-update multiple JSON files")

def save_subject_groups():
    with open(SUBJECTS_JSON, "w", encoding="utf-8") as f:
        json.dump(semester_grouped_subjects, f, indent=4, ensure_ascii=False)
    git_commit_and_push(json_files, "Auto-update multiple JSON files")

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_settings, f, indent=4, ensure_ascii=False)
    git_commit_and_push(json_files, "Auto-update multiple JSON files")

def save_blocked(chat_id):
    global blocked_users
    if chat_id not in blocked_users:
        blocked_users.append(chat_id)
    with open(BLOCKED_FILE, "w", encoding="utf-8") as f:
        json.dump(blocked_users, f, indent=4, ensure_ascii=False)
    git_commit_and_push(json_files, "Auto-update multiple JSON files")

def save_subscribers():
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(subscribers), f, indent=4, ensure_ascii=False)
    git_commit_and_push(json_files, "Auto-update multiple JSON files")


@bot.message_handler(commands=["create_user_data"])

def create_full_data(message, user_id=None):
    """Safely add/update user data without duplicating entries."""
    chat_id = user_id if user_id else message.chat.id

    # Load existing data
    existing_data = user_data_load.get(chat_id, {})
    user_settings = load_json_or_default("user_settings.json", {})

    # User info (prefer existing data if available)
    first_name = message.from_user.first_name or existing_data.get("first_name", "N/A")
    last_name = message.from_user.last_name or existing_data.get("last_name", "N/A")
    username = message.from_user.username or existing_data.get("username", "N/A")

    # Merge user settings with existing data
    settings_data = user_settings.get(str(chat_id), {})
    semester = settings_data.get("semester") or existing_data.get("semester", "N/A")
    department = settings_data.get("department") or existing_data.get("department", "N/A")
    active_settings = bool(settings_data) or existing_data.get("is_settings", False)
    active_sub = chat_id in subscribers or existing_data.get("is_subscribed", False)
    #print(settings_data,semester,department,active_settings)

    # Merge all info into a single dictionary
    updated_data = existing_data.copy()
    updated_data.update({
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "semester": semester,
        "department": department,
        "is_subscribed": active_sub,
        "is_settings": active_settings
    })

    # Save back to global dictionary
    user_data_load[chat_id] = updated_data

    # Save JSON safely
    with open(USER_FULL_DATA, "w") as file:
        json.dump(user_data_load, file, indent=4)

# ------------------------------------------------------------------------------
# /start /help /about
# ------------------------------------------------------------------------------


class UserSession:
    def __init__(self):
        self.conversation_history = []
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')  # Using stable version

    def add_to_history(self, role, text):
        self.conversation_history.append({"role": role, "parts": [text]})
        # Keep only last 10 messages to manage context length
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

    def generate_response(self, user_message):
        try:
            self.add_to_history("user", user_message)
            context = (f"""user message : {user_message}.

                      dont add stars to style the text like **words**""")

            # Create chat session
            chat = self.model.start_chat(history=self.conversation_history)
            response = chat.send_message(context)

            self.add_to_history("model", response.text)

            # Simple chunking for long messages
            return self._split_message(response.text)

        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

    def _split_message(self, text, max_length=4000):
        """Simple and reliable message splitting"""
        if len(text) <= max_length:
            return text

        # Simple chunking - just split at the max length
        chunks = []
        start = 0

        while start < len(text):
            # Get chunk of max_length characters
            end = start + max_length

            # Try to find a good break point (newline or space)
            if end < len(text):
                # Look backwards for a newline break
                break_point = text.rfind('\n', start, end)
                if break_point == -1:
                    # Look for a space break
                    break_point = text.rfind(' ', start, end)
                if break_point == -1:
                    # No good break point, just split at max_length
                    break_point = end
            else:
                break_point = len(text)

            chunk = text[start:break_point].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)

            start = break_point

        return chunks if len(chunks) > 1 else text


class DocumentProcessor:
    @staticmethod
    def extract_text_from_pdf(file_path):
        """Extract text from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            raise Exception(f"PDF extraction error: {str(e)}")

    @staticmethod
    def extract_text_from_docx(file_path):
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"DOCX extraction error: {str(e)}")

    @staticmethod
    def extract_text_from_txt(file_path):
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            raise Exception(f"TXT extraction error: {str(e)}")

    @staticmethod
    def process_document(file_path, file_type):
        """Process document based on file type"""
        if file_type == 'pdf':
            return DocumentProcessor.extract_text_from_pdf(file_path)
        elif file_type == 'docx':
            return DocumentProcessor.extract_text_from_docx(file_path)
        elif file_type == 'txt':
            return DocumentProcessor.extract_text_from_txt(file_path)
        else:
            raise Exception("Unsupported file format")

    @staticmethod
    def summarize_text(text, max_length=1500):
        """Summarize extracted text using Gemini AI"""
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')

            prompt = f"""
            Please provide a comprehensive summary of the following text. 
            Focus on the main points, key findings, and important details.
            Keep the summary clear and well-structured.

            Text to summarize:
            {text[:8000]}  # Limit text length to avoid token limits

            Provide the summary in this format:
            📄 **DOCUMENT SUMMARY**

            **Main Topics:**
            - [List main topics]

            **Key Points:**
            - [List key points]

            **Important Details:**
            - [List important details]

            **Overall Summary:**
            [Brief overall summary]
            """

            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Summarization error: {str(e)}")


# Command handlers
@bot.message_handler(commands=['ai'])
def ai_welcome(message):
    welcome_text = """
🤖 **Welcome to AI Assistant For Study Bot!**

I'm powered by Google Gemini AI. You can:
- Ask me any questions
- Upload documents (PDF, DOCX, TXT) for summarization direct with no need to say summarize!
- Get explanations on various topics
- Have conversations with context awareness

**Supported Files:**
📄 PDF documents
📝 DOCX (Word documents)
📋 TXT files

Just send me a document or message and I'll help you!

**Commands For the Ai:**
/ai - Show this welcome message
/clear - Clear conversation history
/summary - Get info about document summarization
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')


@bot.message_handler(commands=['clear'])
def clear_history(message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        user_sessions[user_id] = UserSession()
    bot.reply_to(message, "✅ Conversation history cleared!")


@bot.message_handler(commands=['summary'])
def summary_info(message):
    info_text = """
📋 **Document Summarization Feature**

I can process and summarize these file types:
• **PDF** - Research papers, reports, articles
• **DOCX** - Word documents, essays, proposals  
• **TXT** - Text files, notes, transcripts

**How to use:**
1. Simply send me a document file
2. I'll extract the text and generate a summary
3. You'll get a structured summary with main points

**What I summarize:**
• Main topics and themes
• Key findings and points
• Important details and conclusions
• Overall document essence

Try it by sending a document! 📄
    """
    bot.reply_to(message, info_text, parse_mode='Markdown')


# Handle document messages
@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        # Show processing status
        bot.send_chat_action(message.chat.id, 'typing')

        # Get file info
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Get file extension
        file_name = message.document.file_name.lower()
        file_extension = Path(file_name).suffix.lower()

        # Check supported formats
        supported_formats = {
            '.pdf': 'pdf',
            '.docx': 'docx',
            '.txt': 'txt',
            '.doc': 'docx'  # Handle .doc as docx
        }

        if file_extension not in supported_formats:
            bot.reply_to(message, f"❌ Unsupported file format: {file_extension}\n\nSupported formats: PDF, DOCX, TXT")
            return

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(downloaded_file)
            temp_path = temp_file.name

        try:
            # Process document
            file_type = supported_formats[file_extension]

            # Send processing message
            processing_msg = bot.reply_to(message, f"📄 Processing {file_name}...")

            # Extract text
            extracted_text = DocumentProcessor.process_document(temp_path, file_type)

            if not extracted_text or len(extracted_text.strip()) < 10:
                bot.edit_message_text(
                    f"❌ Could not extract meaningful text from {file_name}. The document might be scanned or contain only images.",
                    message.chat.id,
                    processing_msg.message_id
                )
                return

            # Generate summary
            bot.edit_message_text(
                f"📊 Analyzing {file_name}... (Extracted {len(extracted_text)} characters)",
                message.chat.id,
                processing_msg.message_id
            )

            summary = DocumentProcessor.summarize_text(extracted_text)

            # Send summary
            response_text = f"""
📄 **Document: {file_name}**
📝 **Summary Generated:**

{summary}

---
_Summary completed successfully! You can now ask questions about this document._
            """

            # Split long messages if needed
            if len(response_text) > 4000:
                chunks = [response_text[i:i + 4000] for i in range(0, len(response_text), 4000)]
                for chunk in chunks:
                    bot.send_message(message.chat.id, chunk, parse_mode='Markdown')
            else:
                bot.edit_message_text(response_text, message.chat.id, processing_msg.message_id)

        finally:
            # Clean up temporary file
            os.unlink(temp_path)

    except Exception as e:
        error_msg = f"❌ Error processing document: {str(e)}"
        bot.reply_to(message, error_msg)



@bot.message_handler(commands=["start"])
def send_welcome(message):
    create_full_data(message)
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    username = f"{first_name} {last_name}".strip() or message.from_user.username
    greetings = [
        f"Hey {username}! 👋 Welcome aboard! Ready to make studying easier?",
        f"Hi {username}, I’m your Study Bot 🤖 — let’s get productive!",
        f"Welcome {username}! 🚀 Use /help to explore what I can do for you.",
        f"Yo {username}! 📚 Ready to dive into lectures, flashcards, and more?",
        f"Nice to see you, {username}! 😄 Type /help to get started.",
    ]
    if message.chat.id in ADMIN_CHAT_ID:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Lecture", callback_data="start_lecture"),
            InlineKeyboardButton("Start Quizz", callback_data="start_quizz"),
            InlineKeyboardButton("Help me", callback_data="start_help"),
            InlineKeyboardButton("Ai", callback_data="start_ai"),
            InlineKeyboardButton("Dash Board", callback_data="start_dash"),
        )
        bot.reply_to(message, random.choice(greetings) + "\nHere our main commands",reply_markup=markup)
    else:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Lecture", callback_data="start_lecture"),
            InlineKeyboardButton("Start Quizz", callback_data="start_quizz"),
            InlineKeyboardButton("Help me", callback_data="start_help"),
            InlineKeyboardButton("Ai", callback_data="start_ai")
        )
        bot.reply_to(message, random.choice(greetings) + "\nHere our main commands",reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("start_"))
def handle_start_command(call):
    action = call.data.split("_")[1]
    user_id = call.from_user.id
    if action == "lecture":
        handle_lecture_entry(call.message,user_id)
    elif action == "quizz":
        start_quiz(call.message)
    elif action == "help":
        send_help(call.message)
    elif action == "dash":
        dash_board(call.message, user_id)
    elif action == "ai":
        ai_welcome(call.message)
@bot.message_handler(commands=["help"])
def send_help(message):
    bot.reply_to(message, HELP)


@bot.message_handler(commands=["dashboard"])
def dash_board(message, user_id=None):
    chat_id = user_id if user_id else message.chat.id
    if chat_id in ADMIN_CHAT_ID:
        settings_data = user_settings.get(str(chat_id), {})
        semester = settings_data.get("semester", "N/A")
        department = settings_data.get("department", "N/A")
        subjects = semester_grouped_subjects.get(semester, {}).get(department, {})
        admin_name = bot.get_chat(chat_id).first_name

        # Get storage size information
        storage_report = get_storage_report(semester, department)

        # Build subjects list
        if not subjects:
            subjects_text = "No Subjects"
        else:
            text_lines = []
            for subject, details in subjects.items():
                count = len(details) if isinstance(details, (dict, list)) else 0
                text_lines.append(f"• <b>{subject}</b> — {count} lectures")
            subjects_text = "\n".join(text_lines)

        # Send the dashboard message
        bot.send_message(
            chat_id,
            f"<b>📊 Dashboard</b>\n"
            f"👤 <b>Admin:</b> {admin_name}\n"
            f"🏫 <b>Semester:</b> {semester.capitalize()}\n"
            f"📚 <b>Department:</b> {department.capitalize()}\n\n"
            f"<b>Storage Summary:</b>\n{storage_report}\n\n"
            f"<b>Subjects:</b>\n{subjects_text}",
            parse_mode="HTML"
        )

    else:
        bot.reply_to(message, "Unauthorized access to dashboard")


def get_storage_report(semester, department):
    """Generate storage report text for the dashboard"""
    if not semester or not department or semester == "N/A" or department == "N/A":
        return "⚠️ Please set semester and department using /settings first"

    try:
        # Check if department and semester exist in data
        if semester not in semester_grouped_subjects:
            return f"❌ No data found for semester: {semester}"

        if department not in semester_grouped_subjects[semester]:
            return f"❌ No data found for department: {department}"

        subjects = semester_grouped_subjects[semester][department]

        if not subjects:
            return f"❌ No subjects found for {department} - {semester}"

        total_department_size_mb = 0
        course_sizes = []

        # Calculate sizes for each course
        for subject_name, lectures in subjects.items():
            if not lectures:
                continue

            course_size_mb = 0
            lecture_count = 0

            for lecture in lectures:
                if lecture.get("file_size_mb"):
                    course_size_mb += lecture["file_size_mb"]
                    lecture_count += 1
                elif lecture.get("file_size_bytes"):
                    # Convert bytes to MB if only bytes are available
                    course_size_mb += lecture["file_size_bytes"] / (1024 * 1024)
                    lecture_count += 1

            total_department_size_mb += course_size_mb

            if course_size_mb > 0:
                course_sizes.append({
                    "name": subject_name,
                    "size_mb": course_size_mb,
                    "lecture_count": lecture_count
                })

        # Create summary report for dashboard
        if not course_sizes:
            return "No storage data available"

        # Sort by size to show top courses
        course_sizes.sort(key=lambda x: x["size_mb"], reverse=True)

        # Create compact storage summary
        summary_lines = [
            f"💾 Total: {total_department_size_mb:.2f} MB",
            f"📚 {len(course_sizes)} courses, {sum(course['lecture_count'] for course in course_sizes)} lectures",
            f"📈 Avg: {total_department_size_mb / len(course_sizes):.2f} MB per course",
            "",
            "<b>Top courses by size:</b>"
        ]

        # Add top 3 largest courses
        for i, course in enumerate(course_sizes[:11], 1):
            size_emoji = "💾"
            if course["size_mb"] > 100:
                size_emoji = "🔥"
            elif course["size_mb"] > 50:
                size_emoji = "⚡"

            summary_lines.append(
                f"{i}. {size_emoji} {course['name']} - {course['size_mb']:.2f} MB"
            )

        if len(course_sizes) > 11:
            summary_lines.append(f"... and {len(course_sizes) - 3} more courses")

        return "\n".join(summary_lines)

    except Exception as e:
        logger.error(f"Error generating storage report: {e}")
        return f"❌ Error calculating storage: {str(e)}"


# Keep the original get_size_command for detailed reports
def get_size_command(message):
    """Get the combined size of lectures for each course based on department and semester."""
    chat_id = message.chat.id

    # Get user settings
    user_setting = user_settings.get(str(chat_id), {})
    semester = user_setting.get("semester")
    department = user_setting.get("department")

    if not semester or not department:
        bot.reply_to(message, "⚠️ Please set semester and department using /settings first")
        return

    try:
        bot.reply_to(message, f"📊 Calculating sizes for {department} - {semester}...")

        # Check if department and semester exist in data
        if semester not in semester_grouped_subjects:
            bot.reply_to(message, f"❌ No data found for semester: {semester}")
            return

        if department not in semester_grouped_subjects[semester]:
            bot.reply_to(message, f"❌ No data found for department: {department}")
            return

        subjects = semester_grouped_subjects[semester][department]

        if not subjects:
            bot.reply_to(message, f"❌ No subjects found for {department} - {semester}")
            return

        total_department_size_mb = 0
        course_sizes = []

        # Calculate sizes for each course
        for subject_name, lectures in subjects.items():
            if not lectures:
                continue

            course_size_mb = 0
            lecture_count = 0

            for lecture in lectures:
                if lecture.get("file_size_mb"):
                    course_size_mb += lecture["file_size_mb"]
                    lecture_count += 1
                elif lecture.get("file_size_bytes"):
                    # Convert bytes to MB if only bytes are available
                    course_size_mb += lecture["file_size_bytes"] / (1024 * 1024)
                    lecture_count += 1

            total_department_size_mb += course_size_mb

            if course_size_mb > 0:
                course_sizes.append({
                    "name": subject_name,
                    "size_mb": course_size_mb,
                    "lecture_count": lecture_count
                })

        # Sort courses by size (largest first)
        course_sizes.sort(key=lambda x: x["size_mb"], reverse=True)

        # Create the report
        report_lines = [
            f"📊 *Storage Report for {department.upper()} - {semester}*",
            "",
            f"*Total Department Size:* {total_department_size_mb:.2f} MB",
            "",
            "*Course Breakdown:*",
            ""
        ]

        # Add each course with its size
        for i, course in enumerate(course_sizes, 1):
            size_emoji = "💾"
            if course["size_mb"] > 100:
                size_emoji = "🔥"
            elif course["size_mb"] > 50:
                size_emoji = "⚡"

            report_lines.append(
                f"{i}. {size_emoji} *{course['name']}*"
            )
            report_lines.append(
                f"   📁 {course['lecture_count']} files | {course['size_mb']:.2f} MB"
            )
            report_lines.append("")

        # Add summary
        report_lines.extend([
            "*Summary:*",
            f"• Total Courses: {len(course_sizes)}",
            f"• Total Lectures: {sum(course['lecture_count'] for course in course_sizes)}",
            f"• Total Size: {total_department_size_mb:.2f} MB",
            f"• Average per Course: {total_department_size_mb / len(course_sizes):.2f} MB" if course_sizes else "• No data"
        ])

        report_text = "\n".join(report_lines)

        # Split message if too long (Telegram limit is 4096 characters)
        if len(report_text) > 4000:
            # Send summary first
            summary_text = "\n".join(report_lines[:5] + report_lines[-5:])
            bot.send_message(chat_id, summary_text, parse_mode="Markdown")

            # Send detailed breakdown in separate message
            detailed_text = "\n".join(report_lines[5:-5])
            bot.send_message(chat_id, detailed_text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, report_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in get_size command: {e}")
        bot.reply_to(message, f"❌ Error calculating sizes: {str(e)}")


@bot.message_handler(commands=["about_me"])
def about_me(message):
    bot.reply_to(
        message,
        (
            f"Study Bot patch {current_version}:\n"
            "I'm a study designed to help you study and access pdfs easily\n"
            "bot created by Awab Azhari\n"
            "Want to find out more about me? Check my website:\n"
            "[Awab Azhari](https://awabazhari.netlify.app)\n"
            "Or find my Facebook page:\n"
            "[Facebook Page](https://www.facebook.com/awabazharii?mibextid=ZbWKwL)"
        ),
        parse_mode="Markdown",
    )

# ------------------------------------------------------------------------------
# Settings flow
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["choose_settings", "set_settings"])
def choose_settings(message: types.Message):
    chat_id = str(message.chat.id)
    current = user_settings.get(chat_id)

    if current:
        current_sem = current.get("semester", "not set").split()[1] if "semester" in current else "not set"
        current_dept = current.get("department", "not set")
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Semester", callback_data="update_semester"),
            InlineKeyboardButton("Department", callback_data="update_department"),
        )
        if current.get("semester").startswith("course"):
            bot.send_message(
            chat_id,
            f"⚙️ You already chose: \n📘 Course : {current_sem}, \n 🏫 Department: {current_dept}\n\nWhat would you like to update?",
            reply_markup=markup,
        )
        elif current.get("semester").startswith("semester"):
            bot.send_message(
            chat_id,
            f"⚙️ You already chose: \n📘 Semester : {current_sem}, \n 🏫 Department: {current_dept} \n\nWhat would you like to update?",
            reply_markup=markup
        )
        return

    ask_for_semester_inline(chat_id, prompt_next=True)

def ask_for_semester_inline(chat_id, prompt_next=False):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("course 1", callback_data="cour_1"),
        InlineKeyboardButton("semester 4", callback_data="sem_4"),
        InlineKeyboardButton("semester 5", callback_data="sem_5"),
        InlineKeyboardButton("semester 6", callback_data="sem_6"),
    )
    prompt = "📘 Please choose your semester:" if not prompt_next else "📘 Please choose your semester to begin setup:"
    bot.send_message(chat_id, prompt, reply_markup=markup)

def ask_for_department_inline(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    departments = ["electronics", "mechatronics", "biomedical", "computer", "t.com", "linux"]
    buttons = [InlineKeyboardButton(dept.title(), callback_data=f"dept_{dept}") for dept in departments]
    markup.add(*buttons)
    bot.send_message(chat_id, "🏫 Now choose your department:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith(("sem_","cour_")))
def handle_semester_choice(call):
    chat_id = str(call.message.chat.id)
    if call.data.startswith("sem_"):
        semester = f"semester {call.data.split('_')[1]}"
        text = f"✅ Semester updated to {semester.split()[1]}"
    elif call.data.startswith("cour_"):
        semester = f"course {call.data.split('_')[1]}"
        text = f"✅ Course updated to {semester.split()[1]}"
    user_settings.setdefault(chat_id, {})["semester"] = semester
    save_settings()

    current_dept = user_settings[chat_id].get("department")
    if current_dept:
        bot.send_message(chat_id,text)
    else:
        ask_for_department_inline(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dept_"))
def handle_department_choice(call):
    chat_id = str(call.message.chat.id)
    department = call.data.split("_")[1]
    user_settings.setdefault(chat_id, {})["department"] = department
    save_settings()

    current_sem = user_settings[chat_id].get("semester")
    if current_sem:
        sem_num = current_sem.split()[1]
        bot.send_message(chat_id, f"✅ Settings saved!\nSemester : {sem_num}, Department: {department.title()}")
    else:
        ask_for_semester_inline(chat_id)

@bot.callback_query_handler(func=lambda call: call.data in ["update_semester", "update_department"])
def handle_update_selection(call):
    if call.data == "update_semester":
        ask_for_semester_inline(call.message.chat.id)
    elif call.data == "update_department":
        ask_for_department_inline(call.message.chat.id)

# New chat member greeting
@bot.message_handler(content_types=["new_chat_members"])
def greet_new_member(message):
    for new_member in message.new_chat_members:
        first_name = new_member.first_name or ""
        last_name = new_member.last_name or ""
        username = f"{first_name} {last_name}".strip()
        bot.send_message(message.chat.id, f"Welcome to the group, {username}! Type /help to get started.")

# ------------------------------------------------------------------------------
# YouTube downloader
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["youtube"])
def youtube(message):
    bot.reply_to(message, "Please send the YouTube video URL you want to download.")
    bot.register_next_step_handler(message, handle_url)

def handle_url(message):
    bot.send_message(message.chat.id, "Fetching data....")
    url = message.text
    user_video_urls[message.chat.id] = url

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "cookiefile": "cookies.txt",
        "geo_bypass": True,
        "concurrent_fragment_downloads": 4,
        "noprogress": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            formats = info_dict.get("formats", [])
            markup = types.InlineKeyboardMarkup(row_width=2)

            added_resolutions = set()
            valid_format_ids = []
            max_resolution = 1440

            for f in formats:
                if f.get("vcodec") != "none":
                    height = f.get("height")
                    if height and height <= max_resolution and height not in added_resolutions:
                        label = f"{height}p"
                        format_id = f["format_id"]
                        markup.add(types.InlineKeyboardButton(label, callback_data=format_id))
                        added_resolutions.add(height)
                        valid_format_ids.append(format_id)

            if not added_resolutions:
                bot.reply_to(message, "No downloadable video formats found.")
                return

            user_format_ids[message.chat.id] = valid_format_ids
            bot.send_message(message.chat.id, "Choose quality:", reply_markup=markup)

    except Exception as e:
        bot.reply_to(message, f"Failed to fetch video info: {e}")

@bot.callback_query_handler(func=lambda call: call.data in user_format_ids.get(call.message.chat.id, []))
def handle_quality(call):
    format_id = call.data
    chat_id = call.message.chat.id
    url = user_video_urls.get(chat_id)

    if not url:
        bot.answer_callback_query(call.id, "Session expired. Please send the URL again.")
        return

    ydl_opts = {
        "format": format_id,
        "cookiefile": "cookies.txt",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "quiet": True,
    }
    bot.send_message(chat_id, "Downloading....")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        with open(file_path, "rb") as video_file:
            bot.send_video(chat_id, video_file)

        os.remove(file_path)
        bot.send_message(chat_id, "Downloaded")
        bot.answer_callback_query(call.id, text="Downloaded successfully!")
    except Exception as e:
        bot.answer_callback_query(call.id, text="Failed")
        bot.send_message(chat_id, f"Error downloading video: {e}")

# ------------------------------------------------------------------------------
# Flashcards: create / delete subjects, add/view/delete cards, import/export CSV
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["create_subject"])
def create_subject(message):
    bot.send_message(message.chat.id, "Please enter the name of the new subject:")
    bot.register_next_step_handler(message, save_new_subject)

def save_new_subject(message):
    subject_name = message.text.strip()
    if subject_name in flashcards_data:
        bot.send_message(
            message.chat.id,
            f"The subject '{subject_name}' already exists. Please use a different name or /add_flashcard to add flashcards.",
        )
    else:
        flashcards_data[subject_name] = {}
        save_flashcards(flashcards_data)
        bot.send_message(
            message.chat.id,
            f"Subject '{subject_name}' created successfully! You can now add flashcards using /add_flashcard.",
        )

@bot.message_handler(commands=["delete_subject"])
def delete_subject(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects are available to delete.")
        return

    markup = InlineKeyboardMarkup()
    for subject in flashcards_data:
        markup.add(InlineKeyboardButton(subject, callback_data=f"delete_subject_{subject.replace(' ', '_')}"))
    bot.send_message(message.chat.id, "Select a subject to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_subject_"))
def confirm_delete_subject(call):
    subject_name = call.data[len("delete_subject_") :].replace("_", " ")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Yes", callback_data=f"confirm_delete_subject_{subject_name.replace(' ', '_')}"))
    markup.add(InlineKeyboardButton("No", callback_data="cancel_delete_subject"))
    bot.send_message(call.message.chat.id, f"Are you sure you want to delete the subject '{subject_name}'?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_subject_") or call.data == "cancel_delete_subject")
def handle_subject_delete_confirmation(call):
    if call.data == "cancel_delete_subject":
        bot.send_message(call.message.chat.id, "Subject deletion canceled.")
        return

    subject_name = call.data[len("confirm_delete_subject_") :].replace("_", " ")
    if subject_name in flashcards_data:
        del flashcards_data[subject_name]
        save_flashcards(flashcards_data)
        bot.send_message(call.message.chat.id, f"Subject '{subject_name}' has been deleted.")
    else:
        bot.send_message(call.message.chat.id, f"Subject '{subject_name}' not found.")

@bot.message_handler(commands=["add_flashcard"])
def request_subject(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available. Please add a new subject first.")
    else:
        markup = create_subject_buttons(action="add_flashcard")
        bot.send_message(message.chat.id, "Choose a subject to add flashcards to:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_flashcard_"))
def get_subject_for_flashcard(call):
    subject = call.data[len("add_flashcard_") :].replace("_", " ")
    user_id = str(call.message.chat.id)

    if subject not in flashcards_data:
        flashcards_data[subject] = {}
    if user_id not in flashcards_data[subject]:
        flashcards_data[subject][user_id] = []

    bot.send_message(call.message.chat.id, f"Adding flashcards to {subject}. Type /done to stop. Send the first question:")
    bot.register_next_step_handler(call.message, lambda msg: process_flashcard(msg, subject))

def process_flashcard(message, subject):
    if message.text.strip().lower() == "/done":
        bot.send_message(message.chat.id, f"Finished adding flashcards to {subject}.")
        return

    question = message.text.strip()
    if not question:
        bot.send_message(message.chat.id, "Empty question. Please try again:")
        bot.register_next_step_handler(message, lambda msg: process_flashcard(msg, subject))
        return

    bot.send_message(message.chat.id, "Now send the answer:")
    bot.register_next_step_handler(message, lambda msg: save_flashcard_and_continue(msg, question, subject))

def save_flashcard_and_continue(message, question, subject):
    answer = message.text.strip()
    if not answer:
        bot.send_message(message.chat.id, "Empty answer. Please try again:")
        bot.register_next_step_handler(message, lambda msg: save_flashcard_and_continue(msg, question, subject))
        return

    user_id = str(message.chat.id)
    flashcards_data[subject][user_id].append({"question": question, "answer": answer})
    save_flashcards(flashcards_data)

    bot.send_message(message.chat.id, f"Flashcard added to {subject}! Send another question or type /done to finish.")
    bot.register_next_step_handler(message, lambda msg: process_flashcard(msg, subject))

@bot.message_handler(commands=["view_flashcards"])
def view_flashcards(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action="view")
        bot.send_message(message.chat.id, "Choose a subject to view flashcards from:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_"))
def show_flashcards(call):
    subject = call.data.split("_", 1)[1]
    user_id = str(call.message.chat.id)
    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])
    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject}.")
    else:
        for index, card in enumerate(user_flashcards):
            bot.send_message(call.message.chat.id, f"Flashcard {index + 1}:\nQ: {card['question']}\nA: {card['answer']}")

@bot.message_handler(commands=["delete_flashcard"])
def delete_flashcard(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action="delete_flashcard")
        bot.send_message(message.chat.id, "Choose a subject to delete flashcards from:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_flashcard_"))
def select_flashcard_to_delete(call):
    subject = call.data[len("delete_flashcard_") :].replace("_", " ")
    user_id = str(call.message.chat.id)
    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])
    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject}.")
    else:
        markup = InlineKeyboardMarkup()
        for index, card in enumerate(user_flashcards):
            markup.add(
                InlineKeyboardButton(
                    text=f"{index + 1}: {card['question'][:30]}...",
                    callback_data=f"confirm_delete_flashcard_{subject.replace(' ', '_')}_{index}",
                )
            )
        bot.send_message(call.message.chat.id, "Select a flashcard to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_flashcard_"))
def delete_selected_flashcard(call):
    parts = call.data[len("confirm_delete_flashcard_") :].rsplit("_", 1)
    subject = parts[0].replace("_", " ")
    index = int(parts[1])
    user_id = str(call.message.chat.id)

    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])
    if 0 <= index < len(user_flashcards):
        deleted = user_flashcards.pop(index)
        save_flashcards(flashcards_data)
        bot.send_message(call.message.chat.id, f"Deleted flashcard:\nQ: {deleted['question']}\nA: {deleted['answer']}")
    else:
        bot.send_message(call.message.chat.id, "Invalid flashcard index.")

@bot.message_handler(commands=["import_flashcards", "export_flashcards"])
def handle_csv(message):
    command = message.text.strip("/").lower()
    if command == "export_flashcards":
        export_flashcards(message.chat.id)
    elif command == "import_flashcards":
        bot.send_message(message.chat.id, "Send the CSV file to import flashcards:")
        bot.register_next_step_handler(message, import_flashcards)

def export_flashcards(chat_id):
    file_path = "/tmp/flashcards.csv"
    # Use utf-8-sig so Excel users don't get mojibake
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Subject", "Question", "Answer"])
        for subject, users in flashcards_data.items():
            for _user_id, flashcards in users.items():
                for card in flashcards:
                    writer.writerow([subject, card.get("question", ""), card.get("answer", "")])

    with open(file_path, "rb") as f:
        bot.send_document(chat_id, f)


def import_flashcards(message):
    import io

    if not getattr(message, "document", None):
        bot.send_message(message.chat.id, "No file sent. Please send a valid CSV file.")
        return

    # Download bytes from Telegram
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # 1) Try a few common encodings
    tried_encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    decoded_text = None
    used_encoding = None
    for enc in tried_encodings:
        try:
            decoded_text = downloaded_file.decode(enc)
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        bot.send_message(
            message.chat.id,
            "Failed to import flashcards: unsupported text encoding. "
            "Please re-save the CSV as UTF-8."
        )
        return

    # 2) Detect delimiter
    sample = "\n".join(decoded_text.splitlines()[:10])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","  # default

    # 3) Read with DictReader
    reader = csv.DictReader(io.StringIO(decoded_text), delimiter=delimiter)

    # Normalize headers (handle typos/variants + BOM)
    def norm(h):
        return (h or "").strip().lower().replace("\ufeff", "")

    headers = [norm(h) for h in (reader.fieldnames or [])]

    # Map possible header variants
    def pick(colnames, options):
        for opt in options:
            if opt in colnames:
                return opt
        return None

    subj_col = pick(headers, {"subject", "subjects"})
    ques_col = pick(headers, {"question", "queastion", "quesion", "q"})
    ans_col  = pick(headers, {"answer", "ans", "a"})

    if not (subj_col and ques_col and ans_col):
        bot.send_message(
            message.chat.id,
            "Failed to import: CSV must have columns for Subject, Question, Answer "
            "(minor typos are accepted, e.g., 'Queastion')."
        )
        return

    # 4) Import rows
    user_id = str(message.chat.id)
    imported = 0
    skipped  = 0

    for raw_row in reader:
        # Access row by normalized keys
        row = {norm(k): v for k, v in raw_row.items()}
        subject  = (row.get(subj_col) or "").strip()
        question = (row.get(ques_col) or "").strip()
        answer   = (row.get(ans_col)  or "").strip()

        # Skip empty/bad rows
        if not subject or (not question and not answer):
            skipped += 1
            continue

        if subject not in flashcards_data:
            flashcards_data[subject] = {}
        if user_id not in flashcards_data[subject]:
            flashcards_data[subject][user_id] = []

        flashcards_data[subject][user_id].append({"question": question, "answer": answer})
        imported += 1

    # 5) Persist and report
    save_flashcards(flashcards_data)
    bot.send_message(
        message.chat.id,
        f"Flashcards imported successfully from {used_encoding}. "
        f"Imported: {imported}, Skipped: {skipped}."
    )


def create_subject_buttons(action="add"):
    markup = InlineKeyboardMarkup()
    for subject in flashcards_data.keys():
        callback_data = f"{action}_{subject.replace(' ', '_')}"
        markup.add(InlineKeyboardButton(subject, callback_data=callback_data))
    return markup

# ------------------------------------------------------------------------------
# Lecture PDFs flow
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["lecture"])
def handle_lecture_entry(message, user_id=None):
    chat_id = str(user_id) if user_id else str(message.chat.id)
    create_full_data(message, user_id)

    settings = user_settings.get(chat_id, {})
    semester = settings.get("semester")
    department = settings.get("department")

    if not semester or not department:
        bot.send_message(chat_id, "⚠️ Please complete your settings using /choose_settings first.")
        return

    subjects = semester_grouped_subjects.get(semester, {}).get(department, {})
    if not subjects:
        bot.send_message(chat_id, f"⚠️ No subjects found for {department} - {semester}")
        return

    markup = InlineKeyboardMarkup()
    for subject in subjects:
        # Shorten callback data if needed
        callback_data = f"show_sub|{semester}|{department}|{subject}"[:64]
        markup.add(InlineKeyboardButton(subject, callback_data=callback_data))

    bot.send_message(chat_id, f"📚 Choose a subject in {department} - {semester}:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("show_sub|"))
def show_subject_lectures(call):
    try:
        _, semester, department, subject = call.data.split("|", 3)
        lectures = semester_grouped_subjects.get(semester, {}).get(department, {}).get(subject, [])

        if not lectures:
            bot.send_message(call.message.chat.id, f"⚠️ No lectures available yet for {subject}.")
            return

        # Group lectures by type and count
        lectures_by_type = {}
        for lecture in lectures:
            lecture_type = lecture.get("lecture_type", "lecture")
            if lecture_type not in lectures_by_type:
                lectures_by_type[lecture_type] = []
            lectures_by_type[lecture_type].append(lecture)

        markup = InlineKeyboardMarkup()

        # Create buttons for each lecture type
        for lecture_type, type_lectures in lectures_by_type.items():
            # Shorten callback data
            callback_data = f"show_type|{semester}|{department}|{subject}|{lecture_type}"[:64]
            display_type = lecture_type.capitalize()
            markup.add(
                InlineKeyboardButton(
                    f"📖 {display_type}s ({len(type_lectures)})",
                    callback_data=callback_data
                )
            )

        # Only show "Download All as ZIP" in main content view (no individual type downloads)
        all_callback = f"dl_all|{semester}|{department}|{subject}"[:64]
        markup.add(InlineKeyboardButton("📦 Download All as ZIP", callback_data=all_callback))

        bot.send_message(call.message.chat.id, f"🎓 Choose a content type for {subject}:", reply_markup=markup)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("show_sub|"))
def show_subject_lectures(call):
    try:
        _, semester, department, subject = call.data.split("|", 3)

        # Get the actual lectures data
        department_data = semester_grouped_subjects.get(semester, {}).get(department, {})
        lectures = department_data.get(subject, [])

        # Debug: Check what we found
        print(f"DEBUG: Looking for {subject} in {department} - {semester}")
        print(f"DEBUG: Found {len(lectures)} lectures")
        if lectures:
            print(f"DEBUG: First lecture: {lectures[0].get('lecture_name', 'No name')}")
            print(f"DEBUG: Lecture types: {list(set(lec.get('lecture_type', 'unknown') for lec in lectures))}")

        if not lectures:
            bot.send_message(call.message.chat.id, f"⚠️ No lectures available yet for {subject}.")
            return

        # Group lectures by type and count
        lectures_by_type = {}
        for lecture in lectures:
            lecture_type = lecture.get("lecture_type", "lecture")  # Default to "lecture" if not specified
            if lecture_type not in lectures_by_type:
                lectures_by_type[lecture_type] = []
            lectures_by_type[lecture_type].append(lecture)

        markup = InlineKeyboardMarkup()

        # Create buttons for each lecture type
        for lecture_type, type_lectures in lectures_by_type.items():
            # Shorten callback data
            callback_data = f"show_type|{semester}|{department}|{subject}|{lecture_type}"[:64]
            display_type = lecture_type.capitalize()
            markup.add(
                InlineKeyboardButton(
                    f"📖 {display_type}s ({len(type_lectures)})",
                    callback_data=callback_data
                )
            )

        # Only show "Download All as ZIP" in main content view
        all_callback = f"dl_all|{semester}|{department}|{subject}"[:64]
        markup.add(InlineKeyboardButton("📦 Download All as ZIP", callback_data=all_callback))

        bot.send_message(call.message.chat.id, f"🎓 Choose a content type for {subject}:", reply_markup=markup)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("show_type|"))
def show_lectures_by_type(call):
    try:
        _, semester, department, subject, lecture_type = call.data.split("|", 4)

        # Get all lectures for this subject
        all_lectures = semester_grouped_subjects.get(semester, {}).get(department, {}).get(subject, [])

        if not all_lectures:
            bot.send_message(call.message.chat.id, f"⚠️ No content available for {subject}.")
            return

        # Debug: Check what we're filtering
        print(f"DEBUG: Filtering {subject} for type: {lecture_type}")
        print(f"DEBUG: Total lectures: {len(all_lectures)}")
        print(f"DEBUG: Available types: {list(set(lec.get('lecture_type', 'unknown') for lec in all_lectures))}")

        # Filter lectures by type - make it case-insensitive and handle missing types
        filtered_lectures = []
        for lecture in all_lectures:
            actual_type = lecture.get("lecture_type", "lecture")  # Default to "lecture"
            # Case-insensitive comparison
            if actual_type.lower() == lecture_type.lower():
                filtered_lectures.append(lecture)

        # If no exact matches, try partial matches
        if not filtered_lectures:
            for lecture in all_lectures:
                actual_type = lecture.get("lecture_type", "lecture")
                if lecture_type.lower() in actual_type.lower() or actual_type.lower() in lecture_type.lower():
                    filtered_lectures.append(lecture)

        print(f"DEBUG: Found {len(filtered_lectures)} lectures after filtering for type '{lecture_type}'")

        if not filtered_lectures:
            # Show all available types to help debug
            available_types = list(set(lec.get("lecture_type", "unknown") for lec in all_lectures))
            error_msg = f"⚠️ No '{lecture_type}' content found for {subject}.\n\nAvailable types: {', '.join(available_types)}"
            bot.send_message(call.message.chat.id, error_msg)
            return

        # Sort by appropriate number field
        if lecture_type.lower() == "lecture":
            filtered_lectures.sort(key=lambda x: x.get("lecture_number", 0))
        elif lecture_type.lower() == "tutorial":
            filtered_lectures.sort(key=lambda x: x.get("tutorial_number", 0))
        else:
            # For other types, try to find any number field
            filtered_lectures.sort(key=lambda x: (
                x.get("lecture_number",
                      x.get("tutorial_number",
                            x.get("number", 0)))
            ))

        markup = InlineKeyboardMarkup()
        for lecture in filtered_lectures:
            # Get the index of this lecture in the original list
            original_index = all_lectures.index(lecture)

            # Create display name
            display_name = ""
            actual_type = lecture.get("lecture_type", "lecture")

            if actual_type.lower() == "lecture":
                lec_num = lecture.get('lecture_number', '')
                display_name = f"Lecture {lec_num}"
            elif actual_type.lower() == "tutorial":
                tut_num = lecture.get('tutorial_number', '')
                display_name = f"Tutorial {tut_num}"
            else:
                display_name = f"{actual_type.capitalize()}"

            # Add lecture name if available
            lecture_name = lecture.get("lecture_name", "")
            if lecture_name:
                # Clean up the name for button display
                clean_name = lecture_name.replace('\n', ' ').replace('  ', ' ')
                short_name = clean_name[:25] + "..." if len(clean_name) > 28 else clean_name
                display_name = f"{display_name}: {short_name}"

            # Shorten callback data
            callback_data = f"send_lec|{semester}|{department}|{subject}|{original_index}"[:64]
            markup.add(InlineKeyboardButton(display_name, callback_data=callback_data))

        # Add download option for this specific type (inside type view)
        dl_callback = f"dl_type|{semester}|{department}|{subject}|{lecture_type}"[:64]
        markup.add(
            InlineKeyboardButton(f"📦 Download All {lecture_type.capitalize()}s as ZIP", callback_data=dl_callback))

        # Add back button
        back_callback = f"show_sub|{semester}|{department}|{subject}"[:64]
        markup.add(InlineKeyboardButton("🔙 Back to Subject", callback_data=back_callback))

        display_type = lecture_type.capitalize()
        bot.send_message(call.message.chat.id, f"🎓 Choose a {lecture_type} for {subject}:", reply_markup=markup)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("send_lec|"))
def send_selected_lecture(call):
    try:
        _, semester, department, subject, index = call.data.split("|", 4)
        lectures = semester_grouped_subjects.get(semester, {}).get(department, {}).get(subject, [])

        try:
            lecture = lectures[int(index)]
        except (IndexError, ValueError):
            bot.send_message(call.message.chat.id, "⚠️ Lecture not found.")
            return

        file_id = lecture.get("file_id")
        file_type = lecture.get("type")
        file_name = lecture.get("file_name", "Lecture")
        lecture_name = lecture.get("lecture_name", file_name)
        lecture_type = lecture.get("lecture_type", "lecture")

        # Create caption
        caption = f"📚 {subject}\n📖 {lecture_name}"

        # Add file size if available
        file_size_mb = lecture.get("file_size_mb")
        if file_size_mb:
            caption += f"\n📦 Size: {file_size_mb} MB"

        # Send file based on type
        if file_type == "document":
            bot.send_document(call.message.chat.id, file_id, caption=caption)
        elif file_type == "video":
            bot.send_video(call.message.chat.id, file_id, caption=caption)
        elif file_type == "photo":
            bot.send_photo(call.message.chat.id, file_id, caption=caption)
        elif file_type == "audio":
            bot.send_audio(call.message.chat.id, file_id, caption=caption)
        else:
            bot.send_message(call.message.chat.id, "⚠️ Unsupported file type.")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error sending lecture: {e}")


def create_zip_from_lectures(lectures, zip_filename, chat_id):
    """Helper function to create ZIP from lectures"""
    try:
        # Create a temporary directory for this operation
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, zip_filename)

            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for i, lecture in enumerate(lectures):
                    try:
                        file_id = lecture.get("file_id")
                        file_info = bot.get_file(file_id)
                        downloaded_file = bot.download_file(file_info.file_path)

                        # Get file extension
                        ext = os.path.splitext(file_info.file_path)[-1] or '.pdf'

                        # Use the original file name or create a descriptive one
                        original_name = lecture.get("file_name", "")
                        if original_name:
                            arcname = original_name
                        else:
                            # Create a descriptive name
                            lecture_type = lecture.get("lecture_type", "file")
                            if lecture_type == "lecture":
                                num = lecture.get("lecture_number", i + 1)
                                arcname = f"{lecture_type}_{num}{ext}"
                            elif lecture_type == "tutorial":
                                num = lecture.get("tutorial_number", i + 1)
                                arcname = f"{lecture_type}_{num}{ext}"
                            else:
                                arcname = f"{lecture_type}_{i + 1}{ext}"

                        # Write to zip
                        zipf.writestr(arcname, downloaded_file)

                    except Exception as e:
                        print(f"Error processing file {i}: {e}")
                        continue

            # Send the ZIP file
            with open(zip_path, 'rb') as f:
                bot.send_document(chat_id, f, caption=f"📦 {zip_filename.replace('.zip', '')}")

            return True

    except Exception as e:
        raise e


@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_type|"))
def download_type_as_zip(call):
    try:
        _, semester, department, subject, lecture_type = call.data.split("|", 4)
        all_lectures = semester_grouped_subjects.get(semester, {}).get(department, {}).get(subject, [])
        bot.send_message(call.message.chat.id, f"Downloading all {lecture_type}s as ZIP....")
        # Filter by type
        filtered_lectures = [lecture for lecture in all_lectures if lecture.get("lecture_type") == lecture_type]

        if not filtered_lectures:
            bot.send_message(call.message.chat.id, f"⚠️ No {lecture_type}s available for {subject}.")
            return

        # Create safe filename
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        zip_filename = f"{safe_subject}_{lecture_type}s.zip"

        # Create and send ZIP directly without processing message
        create_zip_from_lectures(filtered_lectures, zip_filename, call.message.chat.id)

    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error creating {lecture_type}s ZIP: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_all|"))
def download_all_as_zip(call):
    try:
        _, semester, department, subject = call.data.split("|", 3)
        lectures = semester_grouped_subjects.get(semester, {}).get(department, {}).get(subject, [])
        bot.send_message(call.message.chat.id, f"Downloading all lectures as ZIP....")
        if not lectures:
            bot.send_message(call.message.chat.id, f"⚠️ No lectures available yet for {subject}.")
            return

        # Create safe filename
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        zip_filename = f"{safe_subject}_all_materials.zip"

        # Create and send ZIP directly without processing message
        create_zip_from_lectures(lectures, zip_filename, call.message.chat.id)

    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error creating complete ZIP: {e}")

# ------------------------------------------------------------------------------
# Delete subject path / lectures (admin-ish flow)
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["delete_subject_path"])
def delete_subject_command(message):
    chat_id = str(message.chat.id)
    if chat_id not in user_settings:
        bot.send_message(chat_id, "⚠️ Please set your semester and department using /choose_settings.")
        return

    semester = user_settings[chat_id].get("semester")
    department = user_settings[chat_id].get("department")
    if not semester or not department:
        bot.send_message(chat_id, "⚠️ Please complete both semester and department in /choose_settings.")
        return

    subjects = semester_grouped_subjects.get(semester, {}).get(department, {})
    if not subjects:
        bot.send_message(chat_id, f"⚠️ No subjects found for {department} - {semester}")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for subject in subjects:
        markup.add(InlineKeyboardButton(subject, callback_data=f"del_subject_select|{department}|{semester}|{subject}"))

    bot.send_message(chat_id, f"📚 Choose a subject in {department} - {semester} to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_subject_select|"))
def handle_subject_delete_option(call):
    _, dept, sem, subject = call.data.split("|")
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🗑 Delete Entire Subject", callback_data=f"del_subject_confirm|{dept}|{sem}|{subject}"),
        InlineKeyboardButton("❌ Delete All Lectures", callback_data=f"del_subject_clear|{dept}|{sem}|{subject}"),
        InlineKeyboardButton("🧹 Delete Specific Lectures", callback_data=f"del_subject_specific|{dept}|{sem}|{subject}"),
    )
    bot.send_message(call.message.chat.id, f"⚠️ What do you want to do with *{subject}*?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_subject_confirm|") or call.data.startswith("del_subject_clear|"))
def execute_subject_deletion(call):
    action, dept, sem, subject = call.data.split("|")
    if sem not in semester_grouped_subjects or dept not in semester_grouped_subjects.get(sem, {}):
        bot.send_message(call.message.chat.id, "❌ Semester or department not found.")
        return

    if subject not in semester_grouped_subjects[sem][dept]:
        bot.send_message(call.message.chat.id, "❌ Subject not found.")
        return

    if action == "del_subject_confirm":
        del semester_grouped_subjects[sem][dept][subject]
        bot.send_message(call.message.chat.id, f"✅ Subject '{subject}' has been completely removed from {dept} - {sem}.")
    elif action == "del_subject_clear":
        semester_grouped_subjects[sem][dept][subject] = []
        bot.send_message(call.message.chat.id, f"✅ All lectures inside '{subject}' have been deleted, but the subject remains.")

    save_subject_groups()

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_subject_specific|"))
def choose_specific_lecture_to_delete(call):
    _, dept, sem, subject = call.data.split("|")
    lectures = semester_grouped_subjects.get(sem, {}).get(dept, {}).get(subject, [])
    if not lectures:
        bot.send_message(call.message.chat.id, "⚠️ No lectures found to delete.")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for i, _lecture in enumerate(lectures):
        markup.add(InlineKeyboardButton(f"🗑 Delete: Lecture {i + 1}", callback_data=f"del_lecture|{dept}|{sem}|{subject}|{i}"))
    bot.send_message(call.message.chat.id, f"🧹 Select a lecture to delete from *{subject}*:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_lecture|"))
def delete_specific_lecture(call):
    _, dept, sem, subject, idx = call.data.split("|")
    index = int(idx)
    lectures = semester_grouped_subjects.get(sem, {}).get(dept, {}).get(subject, [])
    if index >= len(lectures):
        bot.send_message(call.message.chat.id, "⚠️ Invalid lecture index.")
        return

    lectures.pop(index)
    save_subject_groups()
    bot.send_message(call.message.chat.id, f"✅ Lecture {index + 1} was deleted from {subject}.")

# ------------------------------------------------------------------------------
# Lecture video channels
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["lecture_video"])
def request_department(message):
    bot.send_message(message.chat.id, "Choose your department:", reply_markup=department_buttons("lecture"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("lecture_"))
def handle_lecture_selection(call):
    department = call.data.split("_", 1)[1]
    send_subject_links(call.message, department)

def send_subject_links(message, department):
    subjects = subject_channels.get(department, {})
    if not subjects:
        bot.send_message(message.chat.id, "No channels available for this department yet.")
        return

    markup = types.InlineKeyboardMarkup()
    for subject, link in subjects.items():
        markup.add(types.InlineKeyboardButton(subject, url=link))

    bot.send_message(message.chat.id, "Select a subject to open its channel:", reply_markup=markup)

# ------------------------------------------------------------------------------
# QUIZ (supports Typing & MCQ)
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["start_quiz", "start_quizz"])
def start_quiz(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action="quiz")
        bot.send_message(
            message.chat.id,
            "Choose a subject to start the quiz from:",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("quiz_"))
def quiz_subject(call):
    subject = call.data[len("quiz_") :].replace("_", " ")
    user_id = str(call.message.chat.id)
    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])

    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject} to quiz on.")
        return

    # Store a temporary pre-state (subject only)
    user_quiz_state[call.message.chat.id] = {
        "subject": subject,
        "mode": None,  # 'typing' or 'mcq'
        "questions": [],
        "score": 0,
        "current_index": 0,
        "total": 0,
        "options": None,       # for MCQ current options
        "correct_idx": None,   # for MCQ current correct index
    }

    # Ask for mode
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✍️ Typing", callback_data=f"quizmode|{subject}|typing"),
        InlineKeyboardButton("🔘 MCQ", callback_data=f"quizmode|{subject}|mcq"),
    )
    bot.send_message(call.message.chat.id, "Choose quiz mode:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("quizmode|"))
def quiz_mode_selected(call):
    _, subject, mode = call.data.split("|")
    chat_id = call.message.chat.id
    state = user_quiz_state.get(chat_id)
    if not state or state.get("subject") != subject:
        return

    state["mode"] = mode

    # Determine how many questions user wants (UI buttons: 5, 10, All)
    user_id = str(chat_id)
    total = len(flashcards_data.get(subject, {}).get(user_id, []))
    choices = []
    if total >= 5:
        choices.append(5)
    if total >= 10:
        choices.append(10)
    if total not in choices:
        choices.append(total)
    # ensure uniqueness and order
    choices = sorted(set(choices))

    markup = InlineKeyboardMarkup(row_width=3)
    for n in choices:
        label = f"{n}" if n != total else f"All ({total})"
        markup.add(InlineKeyboardButton(label, callback_data=f"quizlen|{subject}|{mode}|{n}"))
    bot.send_message(chat_id, f"How many questions? (Available: {total})", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("quizlen|"))
def quiz_length_selected(call):
    _, subject, mode, n_str = call.data.split("|")
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    state = user_quiz_state.get(chat_id)
    if not state or state.get("subject") != subject or state.get("mode") != mode:
        return

    try:
        requested = int(n_str)
    except ValueError:
        requested = 1

    # Build questions sample
    cards = flashcards_data.get(subject, {}).get(user_id, [])
    if not cards:
        bot.send_message(chat_id, f"No flashcards found in {subject}.")
        user_quiz_state.pop(chat_id, None)
        return

    if requested > len(cards):
        requested = len(cards)
    questions = random.sample(cards, requested)

    state["questions"] = questions
    state["current_index"] = 0
    state["score"] = 0
    state["total"] = requested
    state["options"] = None
    state["correct_idx"] = None

    bot.answer_callback_query(call.id)
    ask_next_quiz_question(chat_id)

def build_mcq_options(all_cards, correct_card, k=4):
    """Return options list (answers) and index of correct within options."""
    correct = correct_card["answer"].strip()
    # gather distinct wrong answers
    pool = list({c["answer"].strip() for c in all_cards if c is not correct_card and c.get("answer")})
    # ensure at least k-1 wrongs; if not, duplicate some (fallback)
    wrongs = random.sample(pool, min(len(pool), k - 1))
    while len(wrongs) < k - 1 and pool:
        wrongs.append(random.choice(pool))
    options = wrongs + [correct]
    random.shuffle(options)
    correct_idx = options.index(correct)
    return options, correct_idx

def ask_next_quiz_question(chat_id):
    state = user_quiz_state.get(chat_id)
    if state is None:
        return

    if state["current_index"] >= state["total"]:
        score = state["score"]
        total = state["total"]
        bot.send_message(chat_id, f"✅ Quiz completed! Your score: {score}/{total}")
        user_quiz_state.pop(chat_id, None)
        return

    current_card = state["questions"][state["current_index"]]
    state["current_question"] = current_card

    if state["mode"] == "mcq":
        # Build MCQ options
        user_id = str(chat_id)
        all_cards = flashcards_data.get(state["subject"], {}).get(user_id, [])
        options, correct_idx = build_mcq_options(all_cards, current_card, k=4)
        state["options"] = options
        state["correct_idx"] = correct_idx

        letters = ["A", "B", "C", "D"][:len(options)]
        text_lines = [f"Question {state['current_index'] + 1}: {current_card['question']}"]
        for i, opt in enumerate(options):
            text_lines.append(f"{letters[i]}. {opt}")
        msg = "\n".join(text_lines)

        # inline keyboard A/B/C/D
        markup = InlineKeyboardMarkup(row_width=4)
        row = []
        for i, L in enumerate(letters):
            row.append(InlineKeyboardButton(L, callback_data=f"mcq|{i}"))
        markup.add(*row)
        bot.send_message(chat_id, msg, reply_markup=markup)
    else:
        # typing mode
        bot.send_message(chat_id, f"Question {state['current_index'] + 1}: {current_card['question']}")
        bot.register_next_step_handler_by_chat_id(chat_id, check_quiz_answer_typing)

@bot.callback_query_handler(func=lambda call: call.data.startswith("mcq|"))
def handle_mcq_answer(call):
    chat_id = call.message.chat.id
    state = user_quiz_state.get(chat_id)
    if not state or state.get("mode") != "mcq":
        return

    try:
        chosen_idx = int(call.data.split("|")[1])
    except ValueError:
        chosen_idx = -1

    correct_idx = state.get("correct_idx")
    correct_answer = state["options"][correct_idx] if state.get("options") else None

    if chosen_idx == correct_idx:
        state["score"] += 1
        bot.answer_callback_query(call.id, text="✅ Correct!")
        bot.send_message(chat_id, "✅ Correct!")
    else:
        bot.answer_callback_query(call.id, text="❌ Wrong")
        bot.send_message(chat_id, f"❌ Wrong. The correct answer was: {correct_answer}")

    state["current_index"] += 1
    # clear per-question MCQ state
    state["options"] = None
    state["correct_idx"] = None
    ask_next_quiz_question(chat_id)

def check_quiz_answer_typing(message):
    state = user_quiz_state.get(message.chat.id)
    if state is None or state.get("mode") != "typing":
        return

    current_card = state["current_question"]
    user_answer = (message.text or "").strip().lower()
    correct_answer = (current_card["answer"] or "").strip().lower()

    if user_answer == correct_answer:
        bot.send_message(message.chat.id, "✅ Correct!")
        state["score"] += 1
    else:
        bot.send_message(message.chat.id, f"❌ Wrong. The correct answer was: {current_card['answer']}")

    state["current_index"] += 1
    ask_next_quiz_question(message.chat.id)

# ------------------------------------------------------------------------------
# Subscribe / Unsubscribe / Broadcast / Count / Names
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["subscribe"])
def subscribe(message):
    global subscribers
    chat_id = message.chat.id
    if chat_id in subscribers:
        bot.reply_to(message, "You are already subscribed.")
    elif chat_id in blocked_users:
        bot.reply_to(message, "You are not allowed to subscribe.")
    else:
        subscribers.add(chat_id)
        save_subscribers()
        bot.reply_to(message, "You have been subscribed successfully.")

@bot.message_handler(commands=["unsubscribe"])
def unsubscribe(message):
    global subscribers
    chat_id = message.chat.id
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers()
        bot.reply_to(message, "You have been unsubscribed successfully.")
    else:
        bot.reply_to(message, "You are not subscribed.")

@bot.message_handler(commands=["broadcast"])
def broadcast_message(message):
    if message.chat.id in ADMIN_CHAT_ID:
        bot.reply_to(message, "Please send the message or file to broadcast.")
        bot.register_next_step_handler(message, send_broadcast)
    else:
        bot.reply_to(message, "You are not authorized to send broadcast messages.")

def send_broadcast(message):
    if message.text and message.text.lower() == "/cancel":
        cancel(message)
        return

    # Text
    if message.text:
        broadcast_content = message.text
        for chat_id in list(subscribers):
            try:
                bot.send_message(chat_id, broadcast_content)
            except Exception as e:
                print(f"Failed to send message to {chat_id}: {e}")
    # Document
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        for chat_id in list(subscribers):
            try:
                bot.send_document(chat_id, file_id, caption=f"Broadcasting {file_name}")
            except Exception as e:
                print(f"Failed to send document to {chat_id}: {e}")
    # Audio
    elif message.audio:
        file_id = message.audio.file_id
        for chat_id in list(subscribers):
            try:
                bot.send_audio(chat_id, file_id, caption="Broadcasting an audio file.")
            except Exception as e:
                print(f"Failed to send audio to {chat_id}: {e}")
    # Video
    elif message.video:
        file_id = message.video.file_id
        for chat_id in list(subscribers):
            try:
                bot.send_video(chat_id, file_id, caption="Broadcasting a video.")
            except Exception as e:
                print(f"Failed to send video to {chat_id}: {e}")

    bot.reply_to(message, "Broadcast message sent.")

@bot.message_handler(commands=["count"])
def count(message):
    if message.chat.id in ADMIN_CHAT_ID:
        subscribers_count = len(subscribers)
        users_count = len(user_settings)
        bot.send_message(AWAB_CHAT_ID, f"Subscribers are now: {subscribers_count}\nUsers chose settings are now: {users_count}")
    else:
        bot.reply_to(message, "unauthorized access to count")

@bot.message_handler(commands=["nofs"])
def send_subscribers_names(message):
    target_id = None
    if message.chat.id == AWAB_CHAT_ID:
        target_id = AWAB_CHAT_ID
    elif message.chat.id == AMAR_CHAT_ID:
        target_id = AMAR_CHAT_ID
    else:
        bot.reply_to(message, "You are not authorized to access nofs")
        return

    names_list = []
    for chat_id in list(subscribers):
        try:
            user_info = bot.get_chat(chat_id)
            first_name = user_info.first_name or "unknown"
            second_name = user_info.last_name or ""
            user_name = user_info.username or "no username"
            full_name = f"{first_name} {second_name} ({user_name})"
            names_list.append(full_name)
        except telebot.apihelper.ApiTelegramException:
            names_list.append(f"ID: {chat_id} (Name not found)")

    names_text = "\n".join(names_list)
    bot.send_message(target_id, f"Subscribers:\n\n{names_text}")

# ------------------------------------------------------------------------------
# Image <-> PDF
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["img_pdf"])
def img_to_pdf(message):
    bot.reply_to(message, "Please send the images you want to convert to PDF. Send /done_pdf when you are finished.")
    user_data[message.chat.id] = {"images": []}

@bot.message_handler(content_types=["photo"])
def handle_image_for_pdf(message):
    # Only collect photos if user previously initiated /img_pdf
    if message.chat.id not in user_data or "images" not in user_data[message.chat.id]:
        return
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        img_name = f"{message.chat.id}_image_{len(user_data[message.chat.id]['images']) + 1}.jpg"
        with open(img_name, "wb") as new_file:
            new_file.write(downloaded_file)

        user_data[message.chat.id]["images"].append(img_name)
        bot.reply_to(message, f"Image added! You have {len(user_data[message.chat.id]['images'])} image(s). Send /done_pdf to finish.")
    except Exception as e:
        bot.reply_to(message, f"Failed to process image: {e}")

@bot.message_handler(commands=["done_pdf"])
def create_pdf(message):
    images = user_data.get(message.chat.id, {}).get("images", [])
    if not images:
        bot.reply_to(message, "No images were received. Please send images first.")
        return
    bot.reply_to(message, "Enter a name for the PDF (without the .pdf extension):")
    bot.register_next_step_handler(message, name_pdf, images)

def name_pdf(message, images):
    try:
        name = message.text.strip()
        pdf_name = f"{name}.pdf"
        image_objects = [Image.open(img_name).convert("RGB") for img_name in images]
        image_objects[0].save(pdf_name, "PDF", resolution=100.0, save_all=True, append_images=image_objects[1:])

        with open(pdf_name, "rb") as pdf_file:
            bot.send_document(message.chat.id, pdf_file)

        for img_name in images:
            try:
                os.remove(img_name)
            except OSError:
                pass
        try:
            os.remove(pdf_name)
        except OSError:
            pass

        user_data[message.chat.id]["images"] = []
        bot.reply_to(message, "Your PDF has been created successfully!")
    except Exception as e:
        bot.reply_to(message, f"Failed to create PDF: {e}")

@bot.message_handler(commands=["pdf_img"])
def pdf_to_img(message):
    bot.reply_to(message, "Please send the PDF you want to convert to images.")

@bot.message_handler(content_types=["document"])
def handle_pdf_to_img(message):
    # only handle when a PDF is sent (simple check)
    if not message.document or not (message.document.file_name or "").lower().endswith(".pdf"):
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        pdf_name = f"{message.chat.id}_document.pdf"
        with open(pdf_name, "wb") as new_file:
            new_file.write(downloaded_file)

        images = pdf2image.convert_from_path(pdf_name)
        for i, image in enumerate(images):
            image_name = f"page_{i + 1}.jpg"
            image.save(image_name, "JPEG")
            with open(image_name, "rb") as img_file:
                bot.send_photo(message.chat.id, img_file)
            os.remove(image_name)

        os.remove(pdf_name)
    except Exception as e:
        bot.reply_to(message, f"Failed to convert PDF to images: {e}")

# ------------------------------------------------------------------------------
# Reports / Cancel / Donate / IDs
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["report"])
def report_issue(message):
    bot.reply_to(message, "Please describe the issue you're facing:")
    bot.register_next_step_handler(message, handle_report)

def handle_report(message):
    if (message.text or "").lower() == "/cancel":
        cancel(message)
        return
    report_text = (
        f"Report from user <a href='tg://user?id={message.from_user.id}'>"
        f"{message.from_user.first_name} {message.from_user.last_name or ''}</a> : \n\n{message.text}"
    )
    bot.send_message(AWAB_CHAT_ID, report_text, parse_mode="HTML")
    bot.reply_to(message, "Thank you for your report! We'll look into it.")

@bot.message_handler(commands=["cancel"])
def cancel(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.send_message(message.chat.id, "Operation Cancelled")

@bot.message_handler(commands=["donate"])
def donate(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Bankak", callback_data="bankak"))
    markup.add(InlineKeyboardButton("Fawry", callback_data="fawry"))
    bot.reply_to(message, "Welcome to donation, please choose a method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["bankak", "fawry"])
def handle_donation(call):
    user_name = f"{call.from_user.first_name} {call.from_user.last_name or ''}".strip()
    if call.data == "bankak":
        bot.reply_to(call.message, "You chose Bankak")
        bot.send_message(call.message.chat.id, "Account Name:")
        bot.send_message(call.message.chat.id, "Awab Azhari Mohamed Awad")
        bot.send_message(call.message.chat.id, "Account ID:")
        bot.send_message(call.message.chat.id, "4384037")
        bot.reply_to(call.message, "Please confirm the payment by sending the receipt.")
        bot.register_next_step_handler(call.message, handle_payment, user_name)
    elif call.data == "fawry":
        bot.reply_to(call.message, "You chose Fawry")
        bot.send_message(call.message.chat.id, "Account Name:")
        bot.send_message(call.message.chat.id, "Awab Azhari Mohamed Awad")
        bot.send_message(call.message.chat.id, "Account ID:")
        bot.send_message(call.message.chat.id, "51587866")
        bot.reply_to(call.message, "Please confirm the payment by sending the receipt.")
        bot.register_next_step_handler(call.message, handle_payment, user_name)

def handle_payment(message, user_name):
    if message.content_type == "photo":
        photo_id = message.photo[-1].file_id
        bot.send_message(2134611910, f"Payment made from {user_name}")
        bot.send_message(2134611910, "with chat ID")
        bot.send_message(2134611910, message.chat.id)
        bot.send_photo(2134611910, photo_id)
        bot.reply_to(message, "Payment confirmed. Thank you!")
    else:
        bot.reply_to(message, "Please send a valid receipt (document).")
        bot.register_next_step_handler(message, handle_payment, user_name)

@bot.message_handler(commands=["my_id"])
def my_id(message):
    bot.send_message(message.chat.id, message.chat.id)

# ------------------------------------------------------------------------------
# Admin: copy subjects between departments within same semester
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["copy_subject"])
def handle_copy_batch(message):
    if message.chat.id not in ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "Unauthorized access to /copy_subject")
        return

    chat_id = str(message.chat.id)
    semester = user_settings.get(chat_id, {}).get("semester")
    if not semester:
        bot.send_message(chat_id, "⚠️ Please choose your semester first using /choose_settings")
        return

    markup = InlineKeyboardMarkup()
    for department in semester_grouped_subjects.get(semester, {}).keys():
        markup.add(InlineKeyboardButton(f"{semester} - {department}", callback_data=f"copy_src|{semester}|{department}"))
    bot.send_message(message.chat.id, "📌 Select the source department:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_src|"))
def select_subject(call):
    if call.from_user.id != AWAB_CHAT_ID:
        bot.send_message(call.message.chat.id, "⚠️ You don't have permission.")
        return

    _, semester, source_department = call.data.split("|")
    subjects = semester_grouped_subjects.get(semester, {}).get(source_department, {})
    if not subjects:
        bot.send_message(call.message.chat.id, "⚠️ No subjects available in this department.")
        return

    markup = InlineKeyboardMarkup()
    for subject in subjects:
        markup.add(InlineKeyboardButton(subject, callback_data=f"copy_subject|{semester}|{source_department}|{subject}"))
    bot.send_message(call.message.chat.id, f"📌 Select the subject from {source_department} ({semester}):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_subject|"))
def select_target_department(call):
    if call.from_user.id != AWAB_CHAT_ID:
        bot.send_message(call.message.chat.id, "⚠️ You don't have permission.")
        return

    _, semester, source_department, subject_name = call.data.split("|")
    markup = InlineKeyboardMarkup()
    for dept in semester_grouped_subjects.get(semester, {}).keys():
        if dept != source_department:
            markup.add(InlineKeyboardButton(dept, callback_data=f"copy_target|{semester}|{source_department}|{subject_name}|{dept}"))
    bot.send_message(call.message.chat.id, "📌 Select the target department:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_target|"))
def copy_subject(call):
    if call.from_user.id != AWAB_CHAT_ID:
        bot.send_message(call.message.chat.id, "Unauthorized access")
        return

    try:
        _, semester, source_department, subject_name, target_department = call.data.split("|")
        source_subjects = semester_grouped_subjects.get(semester, {}).get(source_department, {})
        if subject_name not in source_subjects:
            bot.send_message(call.message.chat.id, f"⚠️ Subject '{subject_name}' not found in {source_department}.")
            return

        subject_lectures = source_subjects[subject_name]
        target_subjects = semester_grouped_subjects.setdefault(semester, {}).setdefault(target_department, {})
        if subject_name in target_subjects:
            bot.send_message(call.message.chat.id, f"⚠️ Subject '{subject_name}' already exists in {target_department}.")
            return

        target_subjects[subject_name] = copy.deepcopy(subject_lectures)
        save_subject_groups()
        bot.send_message(
            call.message.chat.id,
            f"✅ Successfully copied subject '{subject_name}' from {source_department} to {target_department} in {semester}.",
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error copying subject: {e}")

# ------------------------------------------------------------------------------
# Admin: send messages / send to admins / delete sub
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["send_message"])
def send_message_cmd(message):
    if message.chat.id in ADMIN_CHAT_ID:
        msg = bot.reply_to(message, "Enter the chat ID you want to send the message to:")
        bot.register_next_step_handler(msg, get_target_chat_id)
    else:
        bot.reply_to(message, "Unauthorized access.")


def get_target_chat_id(message):
    try:
        target_chat_id = int(message.text.strip())
        msg = bot.reply_to(message, "Now send the message (text, photo, document, video, etc.) you want to send:")
        bot.register_next_step_handler(msg, send_to_specific_chat, target_chat_id)
    except ValueError:
        bot.reply_to(message, "Invalid chat ID. Please use numbers only.")


def send_to_specific_chat(message, target_chat_id):
    try:
        if message.content_type == 'text':
            bot.send_message(target_chat_id, message.text)
        elif message.content_type == 'photo':
            bot.send_photo(target_chat_id, message.photo[-1].file_id, caption=message.caption or "")
        elif message.content_type == 'video':
            bot.send_video(target_chat_id, message.video.file_id, caption=message.caption or "")
        elif message.content_type == 'document':
            bot.send_document(target_chat_id, message.document.file_id, caption=message.caption or "")
        elif message.content_type == 'audio':
            bot.send_audio(target_chat_id, message.audio.file_id, caption=message.caption or "")
        elif message.content_type == 'voice':
            bot.send_voice(target_chat_id, message.voice.file_id, caption=message.caption or "")
        elif message.content_type == 'sticker':
            bot.send_sticker(target_chat_id, message.sticker.file_id)
        elif message.content_type == 'animation':
            bot.send_animation(target_chat_id, message.animation.file_id, caption=message.caption or "")

        bot.reply_to(message, "✅ Message sent successfully!")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to send: {e}")


def get_message_content(message):
    admin_message = message.text
    msg = bot.reply_to(message, "Enter the recipient's chat ID")
    bot.register_next_step_handler(msg, send_to_recipient, admin_message)

def send_to_recipient(message, admin_message):
    try:
        recipient_id = int(message.text)
        bot.send_message(recipient_id, admin_message)
        bot.reply_to(message, "Message sent successfully!")
    except ValueError:
        bot.reply_to(message, "Invalid chat ID. Please enter a valid number.")

@bot.message_handler(commands=["send_admins"])
def verfiy_admin(message):
    if message.chat.id == AWAB_CHAT_ID:
        msg = bot.send_message(message.chat.id, "Type your message to admins")
        bot.register_next_step_handler(msg, send_to_admins)
    else:
        bot.send_message(message.chat.id, "You are ot allowed to access command")

def send_to_admins(message):
    admin_message = message.text
    for admin in ADMIN_CHAT_ID:
        bot.send_message(admin, admin_message)
    bot.send_message(message.chat.id, "message sent")

@bot.message_handler(commands=["delete_sub"])
def subscriber_id(message):
    if message.chat.id == AWAB_CHAT_ID:
        chat_id_msg = bot.send_message(message.chat.id, "Enter chat id")
        bot.register_next_step_handler(chat_id_msg, delete_sub)
    else:
        bot.send_message(message.chat.id, "You are ot allowed to access command")

def delete_sub(message):
    global subscribers
    try:
        chat_id = int(message.text)
        if chat_id in subscribers:
            subscribers.remove(chat_id)
            save_subscribers()
        save_blocked(chat_id)
        bot.send_message(message.chat.id, "deleted")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid chat id")

# ------------------------------------------------------------------------------
# Upload flow (admin)
# ------------------------------------------------------------------------------
last_upload_time = None

@bot.message_handler(commands=["upload"])
def request_upload_code(message):
    if message.chat.id not in ADMIN_CHAT_ID:
        bot.reply_to(message, "❌ You are not authorized to upload lectures.")
        return

    chat_id = str(message.chat.id)
    semester = user_settings.get(chat_id, {}).get("semester")
    department = user_settings.get(chat_id, {}).get("department")
    if not semester or not department:
        bot.send_message(message.chat.id, "⚠️ Please choose your semester and department first using /choose_settings")
        return

    user_states[message.chat.id] = {"used_markup": False, "semester": semester, "department": department}

    subjects = semester_grouped_subjects.get(semester, {}).get(department, {})
    markup = InlineKeyboardMarkup()
    for subj in subjects:
        markup.add(InlineKeyboardButton(subj, callback_data=f"subject|{semester}|{department}|{subj}"))

    bot.send_message(message.chat.id, f"📚 Choose a subject in {department} ({semester}):", reply_markup=markup)
    bot.send_message(message.chat.id, "Or create a new subject by typing its name.")
    bot.register_next_step_handler(message, process_subject_name)

@bot.callback_query_handler(func=lambda call: call.data.startswith("subject|"))
def handle_subject_selection(call):
    try:
        if user_states.get(call.message.chat.id, {}).get("used_markup"):
            return
        _, semester, department, subject_name = call.data.split("|")
        user_states[call.message.chat.id]["used_markup"] = True
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📂 Subject selected: {subject_name}\nPlease upload your lecture files (PDF, video, etc.). You can upload multiple files.",
        )
        bot.register_next_step_handler(call.message, process_multiple_file_uploads, semester, department, subject_name)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error : {e}")

def process_subject_name(message):
    if message.text and message.text.lower() == "/cancel":
        bot.reply_to(message, "❌ Upload session cancelled.")
        return
    if user_states.get(message.chat.id, {}).get("used_markup"):
        return

    subject_name = (message.text or "").strip()
    semester = user_states[message.chat.id].get("semester")
    department = user_states[message.chat.id].get("department")
    user_states[message.chat.id]["used_markup"] = True

    bot.reply_to(message, f"📂 Subject selected: {subject_name}\nPlease upload your lecture files (PDF, video, etc.). You can upload multiple files.")
    bot.register_next_step_handler(message, process_multiple_file_uploads, semester, department, subject_name)

def process_multiple_file_uploads(message, semester, department, subject_name):
    global last_upload_time
    if not (message.document or message.video or message.photo or message.audio):
        bot.reply_to(message, "❗ Please upload a valid file type (document, video, photo, audio).")
        bot.register_next_step_handler(message, process_multiple_file_uploads, semester, department, subject_name)
        return

    try:
        semester_grouped_subjects.setdefault(semester, {}).setdefault(department, {}).setdefault(subject_name, [])
        group_id = GROUP_IDS.get(department)
        if not group_id:
            bot.reply_to(message, f"⚠️ Group for {department} is not configured.")
            return

        current_index = len(semester_grouped_subjects[semester][department][subject_name]) + 1
        subject_name_split = subject_name.split()
        subject_name_mod = "_".join(subject_name_split)
        content_type = message.content_type
        caption = None
        if content_type == 'document':
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            _, extension = os.path.splitext(message.document.file_name)
            new_name = f"{subject_name_mod}_lec_{current_index}{extension}"
            os.makedirs("temp_uploads", exist_ok=True)
            temp_path = os.path.join("temp_uploads", new_name)
            with open(temp_path, "wb") as f:
                f.write(downloaded_file)
            with open(temp_path, "rb") as f:
                sent_msg = bot.send_document(-4878708176, f, caption=new_name)
            caption = new_name
            file_id = sent_msg.document.file_id
            sent_msg = bot.send_document(group_id, file_id, caption=caption)
            try:
                os.remove(temp_path)
            except Exception as e:
                print(f"Warning: could not delete temp file {temp_path}: {e}")
                bot.send_message(AWAB_CHAT_ID, f"Warning: could not delete temp file {temp_path}: {e}")
        elif content_type == "video":
            file_id = message.video.file_id
            sent_msg = bot.send_video(group_id, file_id, caption=None)
        elif content_type == "photo":
            photo = message.photo[-1]
            file_id = photo.file_id
            sent_msg = bot.send_photo(group_id, file_id, caption=None)
        elif content_type == "audio":
            file_id = message.audio.file_id
            caption = getattr(message.audio, "file_name", None)
            sent_msg = bot.send_audio(group_id, file_id, caption=caption)
        else:
            bot.reply_to(message, "⚠️ Unsupported file type.")
            return

        lecture_data = {
            "message_id": sent_msg.message_id,
            "file_id": file_id,
            "type": content_type,
            "file_name": caption,
        }
        semester_grouped_subjects[semester][department][subject_name].append(lecture_data)
        save_subject_groups()

        bot.reply_to(message, f"✅ File uploaded and sent to the {department} group under subject '{subject_name}'. for  {semester} .")
        bot.reply_to(message, "⏳ You can upload more files or send /cancel to finish.")
        last_upload_time = time.time()
        bot.register_next_step_handler(message, wait_for_timeout, semester, department, subject_name)
    except Exception as e:
        admin_chat_id = message.chat.id
        bot.send_message(message.chat.id, "⚠️ Error: Group may not be configured.")
        try:
            user_chat = bot.get_chat(admin_chat_id)
            first_name = user_chat.first_name or ""
            last_name = user_chat.last_name or ""
            username = user_chat.username or ""
        except Exception:
            first_name = last_name = username = "Unavailable"
        bot.send_message(
            AWAB_CHAT_ID,
            f"⚠️ Error:\n{e}\nUser ID: {admin_chat_id}\nName: {first_name} {last_name}\nUsername: {username}",
        )

def wait_for_timeout(message, semester, department, subject_name):
    global last_upload_time
    if message.text and message.text.lower() == "/cancel":
        bot.reply_to(message, "❌ Upload session cancelled.")
        return

    if message.document or message.video or message.photo or message.audio:
        if time.time() - last_upload_time > 60:
            bot.reply_to(message, "⏳ Timeout reached. Upload session closed.")
            user_states.pop(message.chat.id, None)
            return
        else:
            process_multiple_file_uploads(message, semester, department, subject_name)
            return

    bot.reply_to(message, "❗ Please upload a file or send /cancel to stop.")
    bot.register_next_step_handler(message, wait_for_timeout, semester, department, subject_name)

# ------------------------------------------------------------------------------
# Usage / uptime / misc helpers
# ------------------------------------------------------------------------------
def num_env(name, default):
    raw = os.environ.get(name, "")
    m = re.search(r"[-+]?\d*\.?\d+", raw)
    return float(m.group()) if m else float(default)

@bot.message_handler(commands=["my_usage"])
def my_usage(msg):
    free_left = num_env("RENDER_FREE_HOURS_REMAINING", 0.0)
    free_limit = num_env("RENDER_FREE_HOURS_LIMIT", 750.0)
    bw_used = num_env("RENDER_BW_USED_GB", 0.0)
    bw_limit = num_env("RENDER_BW_LIMIT_GB", 100.0)
    pipe_used = num_env("RENDER_PIPE_USED_MIN", 0.0)
    pipe_limit = num_env("RENDER_PIPE_LIMIT_MIN", 500.0)
    updated_at = os.environ.get("RENDER_USAGE_UPDATED_AT", "—")

    text = (
        "<b>Monthly Included Usage</b>\n\n"
        "🖥️ <b>Free Instance Hours</b>\n"
        f"{free_left:.2f} hours / {free_limit:.0f} hours\n\n"
        "🌐 <b>Included Bandwidth</b>\n"
        f"{bw_used:.0f} GB / {bw_limit:.0f} GB\n\n"
        "🛠️ <b>Included Pipeline Minutes</b>\n"
        f"{pipe_used:.0f} min / {pipe_limit:.0f} min\n\n"
        f"<i>Updated:</i> {updated_at}"
    )
    bot.reply_to(msg, text, disable_web_page_preview=True)

@bot.message_handler(commands=["up_time"])
def up_time(message):
    if message.chat.id in ADMIN_CHAT_ID:
        elapsed_time = time.time() - start_time
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        up_time_str = f"Bot has been running for {int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds."
        bot.reply_to(message, up_time_str)
    else:
        bot.reply_to(message, " You are not authorized to see up time")

# ------------------------------------------------------------------------------
# Simple replies DB-backed (kept)
# ------------------------------------------------------------------------------
conn = sqlite3.connect("bot_responses.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS responses (
        category TEXT NOT NULL,
        trigger TEXT NOT NULL,
        reply   TEXT NOT NULL
    )
"""
)
conn.commit()

def fetch_category_data():
    cursor.execute("SELECT category, trigger, reply FROM responses")
    data = {}
    for category, trigger, reply in cursor.fetchall():
        if category not in data:
            data[category] = {"triggers": [], "replies": []}
        data[category]["triggers"].append(trigger)
        data[category]["replies"].append(reply)
    return data

def load_responses():
    try:
        with open(RESPONSES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

responses = load_responses()

def choose_department(message):
    bot.send_message(message.chat.id, "Choose your department:", reply_markup=department_buttons("lecture"))


@bot.message_handler(func=lambda m: m.text is not None, content_types=["text"])
def handle_text_messages_database(message: types.Message):
    first = message.from_user.first_name or ""
    last = message.from_user.last_name or ""
    username = f"{first} {last}".strip() or message.from_user.username or "there"
    user_id = message.from_user.id
    user_message = message.text
    text = message.text.strip()
    text_lower = text.lower()

    known_cmds = {
        "start",
        "cancel",
        "lecture",
        "img_pdf",
        "pdf_img",
        "create_subject",
        "delete_subject",
        "add_flashcard",
        "view_flashcards",
        "delete_flashcard",
        "import_flashcards",
        "export_flashcards",
        "start_quiz",
        "start_quizz",
        "help",
        "subscribe",
        "unsubscribe",
        "about_me",
        "report",
        "up_time",
        "nofs",
        "count",
        "broadcast",
        "upload",
        "send_message",
        "donate",
        "my_id",
        "lecture_video",
        "upload_video",
        "send_admins",
        "delete_sub",
        "done_pdf",
        "youtube",
        "copy_subject",
        "my_usage",
    }

    # Handle commands starting with /
    if text_lower.startswith("/"):
        cmd = text_lower.split()[0][1:]
        if cmd not in known_cmds:
            bot.reply_to(message, "🤔 That command doesn't exist. Try /help to see what I can do!")
        return

    db_responses = fetch_category_data()

    # SPECIAL CASE: Handle direct lecture requests through existing system
    strong_lecture_phrases = [
        "show me lectures", "get lectures", "open lectures", "find lectures",
        "access lectures", "view lectures", "list lectures", "browse lectures",
        "i want lectures", "need lectures", "lectures please", "open lecture",
        "show lecture", "get lecture", "find lecture", "download lectures",
        "where are lectures", "lecture materials", "course materials"
    ]

    has_strong_lecture_intent = any(phrase in text_lower for phrase in strong_lecture_phrases) or any(word in text_lower for word in db_responses)

    if has_strong_lecture_intent:
        # Directly trigger your lecture system
        handle_lecture_entry(message)
        return

    # Show typing action for AI responses
    bot.send_chat_action(message.chat.id, 'typing')

    # Initialize or get user session for AI
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession()

    # Check for study/lecture related content to provide contextual responses
    study_keywords = ["study", "learn", "course", "class", "education", "subject", "chapter", "topic", "pdf",
                      "material"]
    is_study_related = any(keyword in text_lower for keyword in study_keywords)

    try:
        if is_study_related:
            # Context-aware study response that mentions available commands
            context_prompt = f"""
            User message: "{text}"

            This appears to be study-related. Please provide a helpful educational response.

            IMPORTANT: If they're asking about accessing lectures or what ever they say like lecture me remember its a Study Bot or study materials, naturally mention that they can use:
            - /lecture command for lecture materials
            - Other study features available

            But primarily focus on answering their actual question with educational value.
            Don't force the commands - only mention them if relevant to their query, dont add stars to style the text like **words**, dont talk alot always try to be direct and summarized.
            """
            response = user_sessions[user_id].generate_response(context_prompt)
        else:
            # Regular AI response for general queries
            response = user_sessions[user_id].generate_response(text)

            # Handle both string responses and list of chunks
        if isinstance(response, list):
            for i, chunk in enumerate(response):
                if i == 0:
                    bot.reply_to(message, chunk)
                else:
                    # Add small delay between chunks to avoid rate limiting
                    time.sleep(0.5)
                    bot.send_message(message.chat.id, chunk)
        else:
            bot.reply_to(message, response)

    except Exception as e:
        bot.reply_to(message, f"❌ Error generating response: {str(e)}")

    if message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id:
        bot.reply_to(message, "😅 I’m not sure what you meant try /help to see what I can do!")
        return

    if not response:
        bot.reply_to(message, "🤔 I’m not sure about that. Type /help for a list of commands or ask me something study-related!")


# ------------------------------------------------------------------------------
# Health endpoint
# -----------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Main (Render Web Service: Flask in main thread; polling in background)
# ------------------------------------------------------------------------------
def run_bot():
    # Avoid 409: ensure a single poller & no webhooks
    bot.remove_webhook()
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
        except Exception as e:
            print(e)

if __name__ == "__main__":

    run_bot()

