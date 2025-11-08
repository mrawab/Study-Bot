import os
import time
import re
import shutil
import json
import glob
import threading
import queue
import paramiko
from scp import SCPClient
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import sys
from selenium.webdriver.chrome.service import Service
import zipfile
import telebot
from telebot import types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import telebot.apihelper
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv
load_dotenv()

# ------------------- CONFIGURATION -------------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

ADMIN_CHAT_IDS = [int(x) for x in os.getenv("ADMIN_CHAT_ID").split(",")]

# Elearning credentials
USERNAME = os.getenv("ELEARNING_USERNAME")
PASSWORD = os.getenv("ELEARNING_PASSWORD")

if not USERNAME or not PASSWORD:
    raise ValueError("Elearning credentials are required")

# File paths
SUBJECTS_JSON = "semester_subjects.json"
SETTINGS_FILE = "user_settings.json"
DOWNLOAD_DIR = r"D:\ElearningDownloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Group IDs
GROUP_IDS = {
    "electronics": -1002601636422,
    "mechatronics": -4989575463,
    "biomedical": -4896388043,
    "computer": -4916986833,
    "tcom": -4973193836,
    "linux": -4822189190
}

# Server configuration
SERVER_CONFIG = {
    "hostname": os.getenv("SERVER_HOST"),
    "username": os.getenv("SERVER_USER"),
    "password": os.getenv("SERVER_PASSWORD"),
    "port": int(os.getenv("SERVER_PORT")),
    "remote_json_path": '~/telegram_bot/study_bot/semester_subjects.json',
    "remote_script_path": '~/telegram_bot/study_bot/',
}

# Initialize bot
bot = telebot.TeleBot(TOKEN)
telebot.apihelper.SESSION_TIME_TO_LIVE = 5 * 60

# ------------------- LOGGING SETUP -------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('elearning_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ------------------- CONTEXT MANAGERS -------------------
@contextmanager
def ssh_connection():
    """Context manager for SSH connections."""
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connection_params = {
            'hostname': SERVER_CONFIG['hostname'],
            'port': SERVER_CONFIG['port'],
            'username': SERVER_CONFIG['username'],
            'timeout': 30
        }

        if SERVER_CONFIG.get('password'):
            connection_params['password'] = SERVER_CONFIG['password']
        elif SERVER_CONFIG.get('key_filename'):
            connection_params['key_filename'] = SERVER_CONFIG['key_filename']

        ssh.connect(**connection_params)
        yield ssh
    except Exception as e:
        logger.error(f"SSH connection failed: {e}")
        raise
    finally:
        if ssh:
            ssh.close()


# ------------------- DATA MANAGEMENT -------------------
# ------------------- ENHANCED DATA MANAGEMENT -------------------
class DataManager:
    """Manages JSON data operations with order preservation and safety."""

    @staticmethod
    def load_json_or_default(path: str, default: Any) -> Any:
        """Safely load JSON file with multiple fallback strategies."""
        # Strategy 1: Try to load the main file
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"✅ Successfully loaded {path}")
                return DataManager._ensure_ordered_structure(data)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load {path}: {e}")

        # Strategy 2: Try to find and load the most recent backup
        backup_files = glob.glob(f"{path}.backup_*")
        if backup_files:
            # Sort by creation time (newest first)
            backup_files.sort(key=os.path.getctime, reverse=True)
            latest_backup = backup_files[0]
            try:
                with open(latest_backup, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"✅ Successfully restored from backup: {latest_backup}")

                # Restore the backup to main file
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                return DataManager._ensure_ordered_structure(data)
            except Exception as backup_error:
                logger.error(f"Failed to load backup {latest_backup}: {backup_error}")

        # Strategy 3: Try to load from server if available
        server_data = DataManager.try_load_from_server()
        if server_data:
            logger.info("✅ Successfully loaded data from server")
            # Save locally for future use
            with open(path, "w", encoding="utf-8") as f:
                json.dump(server_data, f, ensure_ascii=False, indent=2)
            return server_data

        # Strategy 4: Use default and create emergency backup
        logger.warning(f"Using default data for {path}")
        DataManager.create_emergency_backup(path)
        return default

    @staticmethod
    def try_load_from_server():
        """Try to load JSON data from server as last resort."""
        try:
            with ssh_connection() as ssh:
                with SCPClient(ssh.get_transport()) as scp:
                    # Download server version to temp file
                    temp_path = "semester_subjects_server_backup.json"
                    scp.get(SERVER_CONFIG['remote_json_path'], temp_path)

                    with open(temp_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Cleanup temp file
                    os.remove(temp_path)
                    return data
        except Exception as e:
            logger.error(f"Failed to load from server: {e}")
            return None

    @staticmethod
    def create_emergency_backup(path: str):
        """Create an emergency backup before using default data."""
        try:
            if os.path.exists(path):
                emergency_backup = f"{path}.emergency_backup"
                shutil.copy2(path, emergency_backup)
                logger.info(f"Created emergency backup: {emergency_backup}")
        except Exception as e:
            logger.error(f"Failed to create emergency backup: {e}")

    @staticmethod
    def save_json(data: Any, path: str) -> bool:
        """Safely save data to JSON file with atomic write and multiple backups."""
        try:
            # Create multiple backups
            if os.path.exists(path):
                # Regular timestamped backup
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                regular_backup = f"{path}.backup_{timestamp}"
                shutil.copy2(path, regular_backup)

                # Keep only last 5 backups
                backup_files = glob.glob(f"{path}.backup_*")
                backup_files.sort(key=os.path.getctime)
                if len(backup_files) > 5:
                    for old_backup in backup_files[:-5]:
                        try:
                            os.remove(old_backup)
                        except:
                            pass

            # Atomic write: write to temp file first, then rename
            temp_path = f"{path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)

            # Replace original file
            if os.path.exists(path):
                os.remove(path)
            os.rename(temp_path, path)

            logger.info(f"✅ Successfully saved {path} with backup")
            return True

        except Exception as e:
            logger.error(f"Error saving {path}: {e}")
            # Try to restore from temp file if possible
            if os.path.exists(temp_path):
                try:
                    shutil.copy2(temp_path, path)
                    logger.info("Restored from temp file after save error")
                except:
                    pass
            return False

    @staticmethod
    def backup_json_files():
        """Create comprehensive backups of JSON files."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S_%f")  # Include microseconds

            for json_file in [SUBJECTS_JSON, SETTINGS_FILE]:
                if os.path.exists(json_file):
                    # Create multiple backup types
                    backups = [
                        f"{json_file}.backup_{timestamp}",
                        f"{json_file}.latest_backup",
                        f"{json_file}.auto_backup"
                    ]

                    for backup_file in backups:
                        try:
                            shutil.copy2(json_file, backup_file)
                        except Exception as e:
                            logger.warning(f"Could not create {backup_file}: {e}")

                    logger.info(f"Created comprehensive backups for {json_file}")

        except Exception as e:
            logger.error(f"Error creating JSON backups: {e}")

    @staticmethod
    def validate_json_data(data: Dict) -> int:
        """Validate and clean the JSON data structure while preserving order."""
        try:
            if not data:
                logger.info("JSON data is empty - nothing to validate")
                return 0

            issues_found = 0

            for semester, departments in data.items():
                if not departments:
                    continue

                for department, subjects in departments.items():
                    if not subjects:
                        continue

                    for subject_name, files in subjects.items():
                        if not files:
                            continue

                        # Remove any entries with missing file_name while preserving order
                        valid_files = []
                        for file_info in files:
                            if file_info.get("file_name") and isinstance(file_info["file_name"], str):
                                valid_files.append(file_info)
                            else:
                                logger.warning(f"Removing invalid file entry from {subject_name}: {file_info}")
                                issues_found += 1

                        # Update with cleaned data (order preserved)
                        data[semester][department][subject_name] = valid_files

            return issues_found

        except Exception as e:
            logger.error(f"JSON validation failed: {e}")
            return -1

    @staticmethod
    def _ensure_ordered_structure(data: Any) -> Any:
        """Recursively ensure data structure preserves order.
        In Python 3.7+, dicts preserve insertion order by default.
        This method ensures we maintain that order when loading from JSON.
        """
        if isinstance(data, dict):
            # Create a new dict to ensure order preservation
            ordered_dict = {}
            for key, value in data.items():
                ordered_dict[key] = DataManager._ensure_ordered_structure(value)
            return ordered_dict
        elif isinstance(data, list):
            # Lists naturally preserve order
            return [DataManager._ensure_ordered_structure(item) for item in data]
        else:
            return data

    @staticmethod
    def add_lecture_to_json(semester: str, department: str, subject_name: str,
                            lecture_data: Dict, json_data: Dict) -> bool:
        """Add a lecture to JSON data while preserving order."""
        try:
            # Initialize the structure if it doesn't exist
            if semester not in json_data:
                json_data[semester] = {}
            if department not in json_data[semester]:
                json_data[semester][department] = {}
            if subject_name not in json_data[semester][department]:
                json_data[semester][department][subject_name] = []

            # Add lecture to the list (preserves order)
            json_data[semester][department][subject_name].append(lecture_data)
            return True

        except Exception as e:
            logger.error(f"Error adding lecture to JSON: {e}")
            return False

    @staticmethod
    def get_subject_lectures(json_data: Dict, semester: str, department: str,
                             subject_name: str) -> List[Dict]:
        """Get lectures for a subject in the order they were added."""
        try:
            return json_data.get(semester, {}).get(department, {}).get(subject_name, [])
        except Exception as e:
            logger.error(f"Error getting subject lectures: {e}")
            return []

    @staticmethod
    def get_lecture_count(json_data: Dict, semester: str, department: str,
                          subject_name: str) -> int:
        """Get the number of lectures for a subject."""
        lectures = DataManager.get_subject_lectures(json_data, semester, department, subject_name)
        return len(lectures)


# Load data
data_manager = DataManager()
semester_grouped_subjects = data_manager.load_json_or_default(SUBJECTS_JSON, {})
user_settings = data_manager.load_json_or_default(SETTINGS_FILE, {})


def stop_server_bot():
    """Stop the bot service on the server using proper sudo authentication."""
    try:
        logger.info("Stopping server bot service...")

        with ssh_connection() as ssh:
            # Method 1: Try using sudo with interactive shell
            shell = ssh.invoke_shell()
            shell.settimeout(10)

            # Send the sudo command
            shell.send('sudo systemctl stop telegrambot\n')
            time.sleep(2)

            # Check if password is required
            output = ""
            while shell.recv_ready():
                output += shell.recv(1024).decode('utf-8')

            if '[sudo] password' in output:
                # Send password
                shell.send(SERVER_CONFIG['password'] + '\n')
                time.sleep(2)

                # Read response
                output = ""
                while shell.recv_ready():
                    output += shell.recv(1024).decode('utf-8')

            shell.close()

            # Verify service is stopped
            stdin, stdout, stderr = ssh.exec_command('systemctl is-active telegrambot')
            status = stdout.read().decode().strip()

            if status == 'inactive':
                logger.info("✅ Server bot service stopped successfully")
                return True, "✅ Server bot stopped successfully"
            else:
                logger.warning(f"Service status: {status}")
                return False, f"⚠️ Service still running: {status}"

    except Exception as e:
        logger.error(f"Server stop failed: {e}")
        return False, f"❌ Server stop failed: {str(e)}"


def restart_server_bot():
    """Restart the bot service on the server after upload."""
    try:
        logger.info("Restarting server bot service...")

        with ssh_connection() as ssh:
            # Use a different approach for sudo commands
            commands = [
                f"cd {SERVER_CONFIG['remote_script_path']}",
                f"echo '{SERVER_CONFIG['password']}' | sudo -S systemctl restart telegrambot"
            ]

            full_command = " && ".join(commands)
            stdin, stdout, stderr = ssh.exec_command(full_command)

            # Wait for command to complete
            stdout.channel.recv_exit_status()

            # Give it a moment to start
            time.sleep(3)

            # Check if service is active
            check_command = "systemctl is-active telegrambot"
            stdin, stdout, stderr = ssh.exec_command(check_command)
            status = stdout.read().decode().strip()

            if status == "active":
                logger.info("✅ Server bot service restarted successfully")
                return True, "✅ Server bot restarted successfully"
            else:
                logger.warning(f"Service might not be running: {status}")
                return False, f"⚠️ Service status: {status}"

    except Exception as e:
        logger.error(f"Server restart failed: {e}")
        return False, f"❌ Server restart failed: {str(e)}"


# ------------------- SELENIUM MANAGER -------------------
class SeleniumManager:
    """Manages Selenium WebDriver with automatic ChromeDriver installation."""

    def __init__(self):
        self.driver = None
        self.max_retries = 2
        self.retry_delay = 3
        self.setup_driver_with_retry()

    def setup_driver_with_retry(self):
        """Setup Chrome driver with retry and auto-install fallback."""
        for attempt in range(self.max_retries):
            try:
                self.setup_driver()
                logger.info(f"✅ Chrome WebDriver initialized successfully (attempt {attempt + 1})")

                # Test the driver with login
                self.login_with_retry()
                return

            except Exception as e:
                logger.error(f"❌ WebDriver initialization failed (attempt {attempt + 1}): {e}")

                if attempt == 0:
                    # Try auto-install on first failure
                    logger.info("🔄 Attempting automatic ChromeDriver installation...")
                    if self.install_chromedriver():
                        continue

                if attempt < self.max_retries - 1:
                    logger.info(f"🔄 Retrying WebDriver initialization in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    if self.driver:
                        try:
                            self.driver.quit()
                        except:
                            pass
                        self.driver = None
                else:
                    raise Exception(f"Failed to initialize WebDriver after {self.max_retries} attempts: {e}")

    def install_chromedriver(self):
        """Automatically download and install ChromeDriver."""
        try:
            logger.info("Downloading ChromeDriver...")

            # Use webdriver_manager for automatic management
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service

                # Install ChromeDriver
                driver_path = ChromeDriverManager().install()
                logger.info(f"✅ ChromeDriver installed at: {driver_path}")
                return True

            except ImportError:
                logger.warning("webdriver_manager not available, trying manual download...")
                return self._download_chromedriver_manual()

        except Exception as e:
            logger.error(f"Auto-installation failed: {e}")
            return False

    def _download_chromedriver_manual(self):
        """Manual ChromeDriver download fallback."""
        try:
            import requests
            import zipfile

            # Download latest stable version
            url = "https://storage.googleapis.com/chrome-for-testing-public/126.0.6478.126/win64/chromedriver-win64.zip"
            zip_path = "chromedriver_temp.zip"

            logger.info("Downloading ChromeDriver...")
            response = requests.get(url, stream=True)
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract to current directory
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall("chromedriver")

            # Move chromedriver.exe to project root or add to PATH
            chromedriver_path = os.path.join("chromedriver", "chromedriver-win64", "chromedriver.exe")
            if os.path.exists(chromedriver_path):
                shutil.copy(chromedriver_path, "chromedriver.exe")
                logger.info("✅ ChromeDriver installed successfully")

            # Cleanup
            os.remove(zip_path)
            shutil.rmtree("chromedriver", ignore_errors=True)
            return True

        except Exception as e:
            logger.error(f"Manual download failed: {e}")
            return False

    def setup_driver(self):
        """Setup Chrome driver with appropriate options."""
        chrome_options = Options()
        chrome_options.add_experimental_option("prefs", {
            "download.default_directory": DOWNLOAD_DIR,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "download.extensions_to_open": "",
            "browser.helperApps.neverAsk.saveToDisk": "application/pdf,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.ms-powerpoint.slideshow.macroEnabled.12,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-word.document.macroEnabled.12"
        })

        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        if os.getenv("DISABLE_IMAGES"):
            chrome_options.add_argument("--disable-images")

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            # Try different methods to initialize driver
            try:
                # Method 1: Try with webdriver_manager
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service

                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)

            except ImportError:
                # Method 2: Try direct initialization (if chromedriver in PATH)
                self.driver = webdriver.Chrome(options=chrome_options)

            self.driver.implicitly_wait(15)
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)

            logger.info("Chrome WebDriver initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            raise

    def login_with_retry(self):
        """Login to elearning platform with retry mechanism."""
        for attempt in range(self.max_retries):
            try:
                self.login()
                logger.info(f"✅ Login successful (attempt {attempt + 1})")
                return
            except Exception as e:
                logger.error(f"❌ Login failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"🔄 Retrying login in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"Failed to login after {self.max_retries} attempts: {e}")

    def login(self):
        """Login to elearning platform."""
        try:
            logger.info("Navigating to elearning login page...")
            self.driver.get("https://elearning.fu.edu.sd/login/index.php")

            # Wait for and fill login form
            username_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.clear()
            username_field.send_keys(USERNAME)

            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(PASSWORD)

            login_btn = self.driver.find_element(By.ID, "loginbtn")
            login_btn.click()

            # Wait for login to complete
            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.CLASS_NAME, "courses"))
            )
            logger.info("Successfully logged in to elearning")

        except TimeoutException:
            logger.error("Login timeout - check credentials or website availability")
            raise
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    def restart_driver(self):
        """Restart the driver if it becomes unresponsive."""
        self.quit()
        self.setup_driver_with_retry()

    def quit(self):
        """Cleanup driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error quitting driver: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()


# ------------------- FILE MANAGEMENT -------------------
class FileManager:
    """Manages file operations and naming with order preservation."""

    @staticmethod
    def detect_lecture_type(lecture_name: str) -> Tuple[str, str]:
        """Detect if lecture is regular, tutorial, or assignment and return type and safe prefix."""
        lecture_lower = lecture_name.lower()

        if any(keyword in lecture_lower for keyword in ["tutorial", "tut"]):
            return "tutorial", "tut"
        elif "assignment" in lecture_lower:
            return "assignment", "assign"
        else:
            return "lecture", "lec"

    @staticmethod
    def generate_safe_filename(safe_name: str, lecture_type: str, type_prefix: str,
                               lecture_number: int, extension: str) -> str:
        """Generate filename with appropriate prefix and numbering."""
        padded_number = f"{lecture_number:02d}"
        return f"{safe_name}_{type_prefix}_{padded_number}{extension}"

    @staticmethod
    def get_next_numbers(course_folder: str, safe_name: str, json_data: Dict, semester: str, department: str,
                         subject_name: str) -> Tuple[int, int, int]:
        """Get the next lecture, tutorial, and assignment numbers for a course."""
        lecture_num = 1
        tutorial_num = 1
        assignment_num = 1

        try:
            # First check JSON data for existing files
            existing_files_info = json_data.get(semester, {}).get(department, {}).get(subject_name, [])

            for file_info in existing_files_info:
                file_name = file_info.get("file_name", "")

                # Check for lectures
                lec_match = re.search(rf"{re.escape(safe_name)}_lec_(\d+)", file_name)
                if lec_match:
                    num = int(lec_match.group(1))
                    if num >= lecture_num:
                        lecture_num = num + 1

                # Check for tutorials
                tut_match = re.search(rf"{re.escape(safe_name)}_tut_(\d+)", file_name)
                if tut_match:
                    num = int(tut_match.group(1))
                    if num >= tutorial_num:
                        tutorial_num = num + 1

                # Check for assignments
                assign_match = re.search(rf"{re.escape(safe_name)}_assign_(\d+)", file_name)
                if assign_match:
                    num = int(assign_match.group(1))
                    if num >= assignment_num:
                        assignment_num = num + 1

            # Then check local files (in case there are files that haven't been uploaded to JSON yet)
            if os.path.exists(course_folder):
                # Patterns for different file types
                lec_pattern = re.compile(rf"{re.escape(safe_name)}_lec_(\d+)")
                tut_pattern = re.compile(rf"{re.escape(safe_name)}_tut_(\d+)")
                assign_pattern = re.compile(rf"{re.escape(safe_name)}_assign_(\d+)")

                for filename in os.listdir(course_folder):
                    # Check for lectures
                    lec_match = lec_pattern.match(filename)
                    if lec_match:
                        num = int(lec_match.group(1))
                        if num >= lecture_num:
                            lecture_num = num + 1

                    # Check for tutorials
                    tut_match = tut_pattern.match(filename)
                    if tut_match:
                        num = int(tut_match.group(1))
                        if num >= tutorial_num:
                            tutorial_num = num + 1

                    # Check for assignments
                    assign_match = assign_pattern.match(filename)
                    if assign_match:
                        num = int(assign_match.group(1))
                        if num >= assignment_num:
                            assignment_num = num + 1

            logger.info(f"Next numbers for {safe_name}: lec={lecture_num}, tut={tutorial_num}, assign={assignment_num}")
            return lecture_num, tutorial_num, assignment_num

        except Exception as e:
            logger.error(f"Error getting next numbers: {e}")
            return lecture_num, tutorial_num, assignment_num

    @staticmethod
    def clean_subject_name(raw_course_name: str) -> Tuple[str, str]:
        """Clean and format subject names for file system use with 18-char limit."""
        # Extract course name after hyphen if present
        if '-' in raw_course_name:
            raw_course_name = raw_course_name.split('-', 1)[1].strip()

        # Remove content in parentheses and clean up
        original_name = re.sub(r"\(.*?\)", "", raw_course_name).strip()

        # Remove the – character and normalize spaces
        original_name = re.sub(r"[–\-]", " ", original_name)
        original_name = re.sub(r"\s+", " ", original_name).strip()

        # Split into words and filter out "and", "or"
        words = original_name.split()
        filtered_words = []

        for word in words:
            lower_word = word.lower()
            # Remove "and", "or" but keep numbers and other words
            if lower_word not in ['and', 'or', '&', 'engineering']:
                filtered_words.append(word)

        # Build JSON subject name with 18-character limit
        json_subject_name = ""
        if len(filtered_words) >= 2:
            # Start with first two words
            json_subject_name = f"{filtered_words[0]} {filtered_words[1]}"

            # Check if we can add a third word (if it's a number/roman numeral and fits)
            if len(filtered_words) >= 3:
                third_word = filtered_words[2]
                # Check if it's a number (digits) or common roman numerals
                if (third_word.isdigit() or
                        third_word.upper() in ['I', 'II', 'III', 'IV', 'V', 'VI', '1', '2', '3', '4', '5', '6']):
                    potential_name = f"{json_subject_name} {third_word}"
                    if len(potential_name) <= 18:
                        json_subject_name = potential_name
        else:
            json_subject_name = original_name

        # Apply 18-character limit (truncate if needed)
        if len(json_subject_name) > 18:
            # Try to find a good truncation point
            if ' ' in json_subject_name:
                # Truncate at the last space before 18 chars
                truncated = json_subject_name[:18]
                last_space = truncated.rfind(' ')
                if last_space > 0:
                    json_subject_name = truncated[:last_space]
                else:
                    json_subject_name = truncated[:18]
            else:
                json_subject_name = json_subject_name[:18]

        # Create safe name for file system (keep original filtered name for file naming)
        safe_name = re.sub(r"\s+", "_", " ".join(filtered_words)).strip()
        safe_name = re.sub(r'[\\/*?:"<>|]', "", safe_name)

        return safe_name, json_subject_name

    @staticmethod
    def generate_ordered_filename(safe_name: str, lecture_number: int, extension: str) -> str:
        """Generate filename with zero-padding for correct ordering."""
        # Use zero-padding for consistent ordering (lec_01, lec_02, ..., lec_10, lec_11)
        padded_number = f"{lecture_number:02d}"  # This gives 01, 02, 03, ..., 10, 11
        return f"{safe_name}_lec_{padded_number}{extension}"

    @staticmethod
    def get_lecture_number_from_filename(filename: str) -> Optional[int]:
        """Extract lecture number from filename for ordering purposes."""
        match = re.search(r"_lec_(\d+)", filename)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def cleanup_downloads():
        """Clean up any residual download files."""
        try:
            for pattern in ["*.crdownload", "*.tmp", "*.part"]:
                for file_path in glob.glob(os.path.join(DOWNLOAD_DIR, pattern)):
                    try:
                        os.remove(file_path)
                        logger.debug(f"Cleaned up: {file_path}")
                    except OSError as e:
                        logger.debug(f"Could not remove {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")

    @staticmethod
    def wait_for_file_download(expected_exts=(".pdf", ".ppt", ".pptx", ".ptx", ".doc", ".docx", ".ppsx"), timeout=120):
        """Wait for file download to complete with better detection."""
        start_time = time.time()

        # Cleanup any previous downloads first
        FileManager.cleanup_downloads()

        # Get initial state of download directory
        initial_files = set()
        try:
            initial_files = set(os.listdir(DOWNLOAD_DIR))
        except Exception as e:
            logger.warning(f"Error reading download directory: {e}")

        logger.info(f"Initial files in download dir: {len(initial_files)}")

        last_incomplete_check = 0
        last_size_check = {}

        while time.time() - start_time < timeout:
            current_time = time.time()

            # Check for incomplete downloads (every 2 seconds)
            if current_time - last_incomplete_check >= 2:
                incomplete_files = (
                        glob.glob(os.path.join(DOWNLOAD_DIR, "*.crdownload")) +
                        glob.glob(os.path.join(DOWNLOAD_DIR, "*.tmp")) +
                        glob.glob(os.path.join(DOWNLOAD_DIR, "*.part"))
                )

                if incomplete_files:
                    logger.debug(f"Download in progress... {len(incomplete_files)} incomplete files")
                    last_incomplete_check = current_time
                    time.sleep(1)
                    continue

            # Check for new completed files
            try:
                current_files = set(os.listdir(DOWNLOAD_DIR))
                new_files = current_files - initial_files

                if new_files:
                    # Check each new file
                    for filename in new_files:
                        file_path = os.path.join(DOWNLOAD_DIR, filename)

                        # Skip directories and system files
                        if not os.path.isfile(file_path) or filename.startswith('.'):
                            continue

                        # Check file extension
                        file_ext = os.path.splitext(filename)[1].lower()
                        if file_ext not in expected_exts:
                            continue

                        # Check if file is still being written
                        try:
                            current_size = os.path.getsize(file_path)

                            # If we've seen this file before, check if size changed
                            if filename in last_size_check:
                                previous_size = last_size_check[filename]
                                if current_size == previous_size and current_size > 0:
                                    # Size hasn't changed - file is complete
                                    logger.info(f"Download completed: {filename} ({current_size} bytes)")
                                    return file_path

                            # Update last known size
                            last_size_check[filename] = current_size

                        except OSError as e:
                            logger.debug(f"File might be locked: {filename} - {e}")
                            continue

                    # If we have new files but none are complete yet, wait a bit
                    time.sleep(1)

                else:
                    # No new files yet
                    time.sleep(2)

            except Exception as e:
                logger.warning(f"Error checking download directory: {e}")
                time.sleep(2)

        logger.error(f"Download timeout after {timeout} seconds")
        # Return the most recently modified file as fallback
        try:
            files = [f for f in os.listdir(DOWNLOAD_DIR)
                     if os.path.isfile(os.path.join(DOWNLOAD_DIR, f)) and
                     not f.startswith('.')]
            if files:
                latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(DOWNLOAD_DIR, f)))
                latest_path = os.path.join(DOWNLOAD_DIR, latest_file)
                logger.warning(f"Timeout - returning most recent file: {latest_file}")
                return latest_path
        except Exception as e:
            logger.error(f"Could not find any downloaded files: {e}")

        return None

    @staticmethod
    def wait_for_file_download_improved(expected_exts=(".pdf", ".ppt", ".pptx", ".ptx", ".ppsx", ".doc", ".docx"),
                                        timeout=30):
        """Improved version that checks for file stability with DOCX/DOC support."""
        start_time = time.time()

        # Track file sizes to detect when download completes
        file_sizes = {}

        while time.time() - start_time < timeout:
            try:
                # Get all files in download directory
                files = [f for f in os.listdir(DOWNLOAD_DIR)
                         if os.path.isfile(os.path.join(DOWNLOAD_DIR, f)) and
                         not f.startswith('.')]

                for filename in files:
                    file_path = os.path.join(DOWNLOAD_DIR, filename)

                    # Skip incomplete download markers
                    if any(filename.endswith(ext) for ext in ['.crdownload', '.tmp', '.part']):
                        continue

                    # Check file extension - ADD DOCX/DOC HERE
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext not in expected_exts:
                        continue

                    try:
                        current_size = os.path.getsize(file_path)

                        # Check if we've seen this file before
                        if filename in file_sizes:
                            if file_sizes[filename] == current_size and current_size > 1000:
                                # File size hasn't changed and it's not empty - download complete!
                                logger.info(f"Download stable: {filename} ({current_size} bytes)")
                                return file_path

                        # Update the size record
                        file_sizes[filename] = current_size

                    except OSError:
                        continue

            except Exception as e:
                logger.debug(f"Error checking files: {e}")

            time.sleep(1)

        # If timeout, return the largest stable file we found
        stable_files = {f: s for f, s in file_sizes.items() if s > 1000}
        if stable_files:
            largest_file = max(stable_files, key=stable_files.get)
            file_path = os.path.join(DOWNLOAD_DIR, largest_file)
            logger.warning(f"Timeout - returning largest stable file: {largest_file}")
            return file_path

        return None

    @staticmethod
    def organize_course_files(course_folder: str, safe_name: str):
        """Organize files in course folder with proper numbering."""
        try:
            if not os.path.exists(course_folder):
                return

            # Pattern to match lecture files
            pattern = re.compile(rf"{re.escape(safe_name)}_lec_(\d+)(?:_\d+)?\.\w+")

            files = []
            for filename in os.listdir(course_folder):
                match = pattern.match(filename)
                if match:
                    lecture_num = int(match.group(1))
                    files.append((lecture_num, filename))

            # Sort by lecture number
            files.sort(key=lambda x: x[0])

            logger.info(f"Found {len(files)} lecture files in {course_folder}")
            return files

        except Exception as e:
            logger.error(f"Error organizing course files: {e}")
            return []

    @staticmethod
    def create_course_structure(semester: str, department: str, subject_name: str) -> str:
        """Create organized folder structure for course files."""
        try:
            # Create semester/department/subject structure
            semester_folder = os.path.join(DOWNLOAD_DIR, semester)
            department_folder = os.path.join(semester_folder, department)
            course_folder = os.path.join(department_folder, subject_name)

            os.makedirs(course_folder, exist_ok=True)
            logger.info(f"Created course structure: {course_folder}")
            return course_folder

        except Exception as e:
            logger.error(f"Error creating course structure: {e}")
            # Fallback to simple structure
            return os.path.join(DOWNLOAD_DIR, subject_name)

    @staticmethod
    def backup_json_files():
        """Create timestamped backups of JSON files."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")

            for json_file in [SUBJECTS_JSON, SETTINGS_FILE]:
                if os.path.exists(json_file):
                    backup_file = f"{json_file}.backup_{timestamp}"
                    shutil.copy2(json_file, backup_file)
                    logger.info(f"Created backup: {backup_file}")

        except Exception as e:
            logger.error(f"Error creating JSON backups: {e}")

    @staticmethod
    def validate_file_integrity(file_path: str, min_size_bytes: int = 1000) -> bool:
        """Validate that a file exists and meets minimum size requirements."""
        try:
            if not os.path.exists(file_path):
                return False

            file_size = os.path.getsize(file_path)
            if file_size < min_size_bytes:
                logger.warning(f"File too small: {file_path} ({file_size} bytes)")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating file integrity: {e}")
            return False


# ------------------- COURSE MANAGEMENT -------------------
class CourseManager:
    """Manages course and lecture collection with order preservation."""

    def __init__(self, selenium_manager: SeleniumManager):
        self.selenium = selenium_manager

    def collect_courses(self) -> Dict[str, str]:
        """Collect ALL available courses from the dashboard without filtering."""
        try:
            courses = {}
            # Use more specific selector for course links
            course_links = self.selenium.driver.find_elements(
                By.CSS_SELECTOR, "h4.card-title a"
            )

            for link in course_links:
                try:
                    course_name = link.text.strip()
                    if course_name:
                        courses[course_name] = link.get_attribute("href")
                except Exception as e:
                    logger.debug(f"Error processing course link: {e}")
                    continue

            logger.info(f"Found {len(courses)} total courses")
            return courses

        except Exception as e:
            logger.error(f"Error collecting courses: {e}")
            return {}

    def collect_lectures(self, course_url: str) -> List[Dict]:
        """Collect lectures from a course page while preserving original order."""
        lectures = []

        try:
            self.selenium.driver.get(course_url)
            WebDriverWait(self.selenium.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.activityinstance"))
            )

            lecture_links = self.selenium.driver.find_elements(
                By.CSS_SELECTOR, "div.activityinstance a.aalink"
            )

            for link in lecture_links:
                try:
                    name = link.find_element(By.CSS_SELECTOR, "span.instancename").text.strip()

                    # Clean the name but keep tutorial/assignment keywords
                    name = re.sub(r"\s*(File|Quiz|External tool)\s*", "", name, flags=re.IGNORECASE).strip()

                    # Skip unwanted content (but keep assignments for processing)
                    if any(x in name.lower() for x in ["midterm", "final", "quiz", "smowl"]):
                        continue

                    # Check file type via icon - ADD DOCX/DOC DETECTION
                    img = link.find_element(By.TAG_NAME, "img")
                    img_src = img.get_attribute("src").lower()

                    if "mp3" in img_src or "audio" in img_src:
                        logger.info(f"Skipping audio file: {name}")
                        continue
                    elif not any(ext in img_src for ext in
                                 ["pdf", "pptx", "powerpoint", "ppt", "ptx", "document", "ppsx", "pps", "word", "doc",
                                  "docx"]):
                        logger.info(f"Skipping non-PDF/PPTX/PPSX/DOCX: {name} (img_src: {img_src})")
                        continue

                    # Add to lectures list (preserving order)
                    lecture_url = link.get_attribute("href")
                    lecture_data = {
                        "name": name,
                        "url": lecture_url,
                        "original_order": len(lectures) + 1  # Track original position
                    }
                    lectures.append(lecture_data)

                    # Log the type detection for debugging
                    lecture_type, prefix = FileManager.detect_lecture_type(name)
                    logger.info(f"Found {lecture_type} [{len(lectures)}]: {name}")

                except Exception as e:
                    logger.warning(f"Error processing lecture link: {e}")
                    continue

            logger.info(f"Successfully collected {len(lectures)} lectures in order")
            return lectures

        except TimeoutException:
            logger.error(f"Timeout waiting for lectures to load in {course_url}")
            return []
        except Exception as e:
            logger.error(f"Error collecting lectures from {course_url}: {e}")
            return []


@bot.message_handler(commands=["preview_changes"])
def preview_changes_command(message):
    """Preview how real courses will be named in the next upload."""
    if message.chat.id not in ADMIN_CHAT_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        bot.reply_to(message, "🔄 Collecting real courses for upload preview...")

        with SeleniumManager() as selenium:
            course_manager = CourseManager(selenium)
            courses = course_manager.collect_courses()

            if not courses:
                bot.send_message(message.chat.id, "❌ No courses found on dashboard.")
                return

            preview_lines = ["🔍 *Upload Preview - How Courses Will Be Named:*", ""]
            preview_lines.append(f"*Found {len(courses)} courses on dashboard*")

            # Show all courses with their conversions
            for i, (course_name, course_url) in enumerate(courses.items(), 1):
                safe_name, json_name = FileManager.clean_subject_name(course_name)
                length = len(json_name)

                # Status indicators
                if length <= 18:
                    status = "✅"
                    status_text = "GOOD"
                elif length <= 22:
                    status = "⚠️"
                    status_text = "WARNING"
                else:
                    status = "❌"
                    status_text = "TOO LONG"

                preview_lines.append(f"**Course #{i}** - {status} {status_text} ({length}/18 chars)")
                preview_lines.append(f"📝 *Original:* {course_name}")
                preview_lines.append(f"📋 *JSON Name:* `{json_name}`")
                preview_lines.append(f"💾 *File Name:* `{safe_name}_lec_01.pdf`")
                preview_lines.append("")

                # Limit to avoid Telegram message limits
                if i >= 12:  # Show first 12 courses
                    remaining = len(courses) - 12
                    if remaining > 0:
                        preview_lines.append(f"📚 *... and {remaining} more courses*")
                    break

            preview_text = "\n".join(preview_lines)

            # Send the main preview
            bot.send_message(message.chat.id, preview_text, parse_mode="Markdown")

            # Send summary statistics
            total_courses = len(courses)
            shown_courses = min(12, total_courses)

            # Analyze all courses for statistics
            name_lengths = []
            status_counts = {"✅": 0, "⚠️": 0, "❌": 0}

            for course_name in courses.keys():
                _, json_name = FileManager.clean_subject_name(course_name)
                length = len(json_name)
                name_lengths.append(length)

                if length <= 18:
                    status_counts["✅"] += 1
                elif length <= 22:
                    status_counts["⚠️"] += 1
                else:
                    status_counts["❌"] += 1

            avg_length = sum(name_lengths) / len(name_lengths) if name_lengths else 0

            summary = (
                f"📊 *Upload Preview Summary:*\n\n"
                f"• Total courses: {total_courses}\n"
                f"• Average name length: {avg_length:.1f} chars\n"
                f"• ✅ Good (≤18 chars): {status_counts['✅']} courses\n"
                f"• ⚠️ Warning (19-22 chars): {status_counts['⚠️']} courses\n"
                f"• ❌ Too long (>22 chars): {status_counts['❌']} courses\n\n"
                f"*Ready for upload? Use /upload to start!*"
            )

            bot.send_message(message.chat.id, summary, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Preview changes failed: {e}")
        bot.send_message(message.chat.id, f"❌ Preview failed: {e}")


# ------------------- DOWNLOAD MANAGER -------------------
class DownloadManager:
    """Manages file downloads and uploads sequentially (one at a time)."""

    def __init__(self, bot, selenium_manager: SeleniumManager):
        self.bot = bot
        self.selenium = selenium_manager
        self.uploaded_files_report = {"uploaded": [], "skipped": [], "failed": [], "recovered": []}

    def process_course_sequentially(self, courses: Dict[str, str], chat_id: int, department: str, semester: str):
        """Process all courses sequentially, one lecture at a time."""
        total_courses = len(courses)
        processed_courses = 0

        for course_name, course_url in courses.items():
            processed_courses += 1
            safe_name, original_name = FileManager.clean_subject_name(course_name)

            self.bot.send_message(chat_id, f"📖 Processing ({processed_courses}/{total_courses}): {original_name}")
            logger.info(f"Processing course {processed_courses}/{total_courses}: {original_name}")

            try:
                # Collect lectures for this course
                course_manager = CourseManager(self.selenium)
                lectures = course_manager.collect_lectures(course_url)

                if not lectures:
                    self.bot.send_message(chat_id, f"⚠️ No lectures found for: {original_name}")
                    continue

                # Process lectures sequentially
                self.process_lectures_sequentially(
                    lectures, original_name, safe_name, chat_id, department, semester
                )

            except TimeoutException as e:
                error_msg = f"❌ Timeout processing course '{original_name}': {str(e)}"
                logger.error(error_msg)
                self.bot.send_message(chat_id, error_msg)
                continue
            except Exception as e:
                error_msg = f"❌ Error processing course '{original_name}': {str(e)}"
                logger.error(error_msg)
                self.bot.send_message(chat_id, error_msg)
                continue

    def process_lectures_sequentially(self, lectures: List[Dict], original_name: str, safe_name: str,
                                      chat_id: int, department: str, semester: str):
        """Process lectures for a course one at a time with proper naming."""
        course_folder = FileManager.create_course_structure(semester, department, original_name)

        total_lectures = len(lectures)

        # Get existing files info for this course
        existing_files_info = semester_grouped_subjects.get(semester, {}).get(department, {}).get(original_name, [])

        # Create sets for duplicate detection
        existing_lecture_names = {file_info["lecture_name"] for file_info in existing_files_info}
        existing_file_names = {file_info["file_name"] for file_info in existing_files_info}

        # Track downloaded URLs to prevent processing the same file multiple times
        processed_urls = set()

        # Get next numbers for each type - NOW INCLUDES JSON DATA
        next_lec_num, next_tut_num, next_assign_num = FileManager.get_next_numbers(
            course_folder, safe_name, semester_grouped_subjects, semester, department, original_name
        )

        # Initialize counters
        current_lec_num = next_lec_num
        current_tut_num = next_tut_num
        current_assign_num = next_assign_num

        # Process lectures in their original order
        for lecture_index, lecture_data in enumerate(lectures, 1):
            lecture_name = lecture_data["name"]
            lecture_url = lecture_data["url"]
            original_order = lecture_data.get("original_order", lecture_index)

            # Skip if we've already processed this URL (same file linked multiple times)
            if lecture_url in processed_urls:
                self.uploaded_files_report["skipped"].append(f"{lecture_name} (duplicate URL)")
                self.bot.send_message(chat_id, f"⏭️ Skipped duplicate URL: {lecture_name}")
                continue

            processed_urls.add(lecture_url)

            self.bot.send_message(chat_id,
                                  f"📚 Lecture {lecture_index}/{total_lectures}: {lecture_name}")

            # Check if already exists by name
            if lecture_name in existing_lecture_names:
                self.uploaded_files_report["skipped"].append(lecture_name)
                self.bot.send_message(chat_id, f"⏭️ Skipped (already exists): {lecture_name}")
                continue

            try:
                # Detect lecture type and get appropriate prefix with improved detection
                lecture_type, type_prefix = self.detect_lecture_type_improved(lecture_name)

                # Determine which counter to use
                if lecture_type == "tutorial":
                    lecture_number = current_tut_num
                elif lecture_type == "assignment":
                    lecture_number = current_assign_num
                else:
                    lecture_number = current_lec_num

                # Download the lecture with appropriate naming
                file_path = self.download_single_lecture(
                    lecture_url, course_folder, safe_name,
                    lecture_type, type_prefix, lecture_number,
                    lecture_name, chat_id
                )

                if file_path:
                    # Check for duplicate content BEFORE uploading
                    # In process_lectures_sequentially, replace the duplicate check:
                    # Check for duplicate content BEFORE uploading
                    is_duplicate = self.is_duplicate_file(file_path, existing_files_info, lecture_name)
                    if is_duplicate:
                        self.uploaded_files_report["skipped"].append(f"{lecture_name} (duplicate content)")
                        self.bot.send_message(chat_id, f"⏭️ Skipped (duplicate content): {lecture_name}")
                        try:
                            os.remove(file_path)  # Clean up the downloaded file
                        except:
                            pass

                        # If it's a duplicate, we still need to increment the counter
                        # to avoid reusing the same number for the next file
                        if lecture_type == "tutorial":
                            current_tut_num += 1
                        elif lecture_type == "assignment":
                            current_assign_num += 1
                        else:
                            current_lec_num += 1
                        continue

                    # Check if file with same name already exists in JSON
                    # Get the actual file extension for the check
                    actual_extension = os.path.splitext(file_path)[1]
                    expected_filename = f"{safe_name}_{type_prefix}_{lecture_number:02d}{actual_extension}"
                    if expected_filename in existing_file_names:
                        self.uploaded_files_report["skipped"].append(f"{lecture_name} (file already uploaded)")
                        self.bot.send_message(chat_id, f"⏭️ Skipped (file already uploaded): {lecture_name}")
                        try:
                            os.remove(file_path)
                        except:
                            pass

                        # Increment counter even if skipped due to filename conflict
                        if lecture_type == "tutorial":
                            current_tut_num += 1
                        elif lecture_type == "assignment":
                            current_assign_num += 1
                        else:
                            current_lec_num += 1
                        continue

                    # Upload to Telegram
                    success = self.upload_single_lecture(
                        file_path, lecture_name, chat_id, department,
                        semester, original_name, lecture_number, lecture_type, type_prefix
                    )

                    # Only increment counter if upload was successful
                    if success:
                        if lecture_type == "tutorial":
                            current_tut_num += 1
                        elif lecture_type == "assignment":
                            current_assign_num += 1
                        else:
                            current_lec_num += 1
                else:
                    self.uploaded_files_report["failed"].append(f"{lecture_name} (download failed)")
                    self.bot.send_message(chat_id, f"❌ Download failed: {lecture_name}")

            except Exception as e:
                error_msg = f"❌ Error processing '{lecture_name}': {str(e)}"
                logger.error(error_msg)
                self.bot.send_message(chat_id, error_msg)
                self.uploaded_files_report["failed"].append(f"{lecture_name} ({str(e)})")

    def detect_lecture_type_improved(self, lecture_name: str) -> Tuple[str, str]:
        """Improved lecture type detection with better logic."""
        lecture_lower = lecture_name.lower().strip()

        # More specific patterns for tutorials
        tutorial_patterns = [
            r'\btutorial\s*\d+',
            r'\btut\.?\s*\d+',
            r'\btut\s+\d+',
            r'^tutorial$',
            r'^tut\.?$'
        ]

        # More specific patterns for assignments
        assignment_patterns = [
            r'\bassignment\s*\d+',
            r'\bass\.?\s*\d+',
            r'\bass\s+\d+',
            r'^assignment$',
            r'^ass\.?$',
            r'\bhw\s*\d+',  # homework
            r'\bhomework\s*\d+'
        ]

        # Check for tutorials first (more specific)
        for pattern in tutorial_patterns:
            if re.search(pattern, lecture_lower):
                return "tutorial", "tut"

        # Check for assignments
        for pattern in assignment_patterns:
            if re.search(pattern, lecture_lower):
                return "assignment", "assign"

        # Default to lecture
        return "lecture", "lec"

    def is_duplicate_file(self, file_path: str, existing_files_info: List[Dict], current_lecture_name: str) -> bool:
        """Check if a file is a duplicate by comparing file size and lecture name."""
        try:
            if not os.path.exists(file_path):
                return False

            current_size = os.path.getsize(file_path)
            current_name = os.path.basename(file_path)

            # Extract current file type and number for better comparison
            current_pattern = re.compile(rf'(.+)_(lec|tut|assign)_(\d+)\.\w+$')
            current_match = current_pattern.match(current_name)

            current_type = current_match.group(2) if current_match else ""

            for existing_file in existing_files_info:
                existing_name = existing_file["file_name"]
                existing_size = existing_file.get("file_size_bytes", 0)
                existing_lecture_name = existing_file.get("lecture_name", "")
                existing_type = existing_file.get("type_prefix", "")

                # Extract existing file type and number
                existing_match = current_pattern.match(existing_name)
                existing_num = int(existing_match.group(3)) if existing_match else 0

                # Only check for duplicates if:
                # 1. File sizes are exactly the same (byte-per-byte match)
                # 2. AND lecture names are very similar
                # 3. AND they are the same type (both tutorials, both lectures, etc.)
                if (current_size == existing_size and
                        current_type == existing_type and
                        self.lecture_names_very_similar(current_lecture_name, existing_lecture_name)):
                    logger.info(
                        f"Duplicate detected: '{current_lecture_name}' ({current_size} bytes, {current_type}) matches '{existing_lecture_name}'")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False

    def lecture_names_very_similar(self, name1: str, name2: str) -> bool:
        """Strict check if two lecture names are very similar."""

        def clean_name(name):
            # Remove content in parentheses and normalize
            name = name.lower().strip()
            name = re.sub(r'\([^)]*\)', '', name)  # Remove parentheses content
            name = re.sub(r'[^\w\s]', ' ', name)  # Remove special chars
            name = re.sub(r'\s+', ' ', name).strip()  # Normalize spaces
            # Remove common words that don't affect meaning
            common_words = {'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of'}
            words = [word for word in name.split() if word not in common_words]
            return ' '.join(words)

        clean1 = clean_name(name1)
        clean2 = clean_name(name2)

        # If cleaned names are identical, they're similar
        if clean1 == clean2:
            return True

        # For tutorial names like "Tutorial 1", "Tutorial 2" - they're different
        if re.match(r'^tutorial\s+\d+$', clean1) and re.match(r'^tutorial\s+\d+$', clean2):
            return clean1 == clean2  # Only same if same tutorial number

        # Calculate word overlap with strict threshold
        words1 = set(clean1.split())
        words2 = set(clean2.split())

        if len(words1) == 0 or len(words2) == 0:
            return False

        overlap = len(words1.intersection(words2))
        min_length = min(len(words1), len(words2))

        # Require high similarity (85%) to consider duplicates
        similarity_ratio = overlap / min_length if min_length > 0 else 0

        return similarity_ratio > 0.85

    def filenames_similar(self, name1: str, name2: str) -> bool:
        """Check if two filenames are similar (same base name, different prefixes)."""
        # Extract base names without prefixes and extensions
        base1 = re.sub(r'^(lec|tut|assign)_\d+', '', name1).replace('.pdf', '')
        base2 = re.sub(r'^(lec|tut|assign)_\d+', '', name2).replace('.pdf', '')

        return base1 == base2

    def download_single_lecture(self, url: str, course_folder: str, safe_name: str,
                                lecture_type: str, type_prefix: str, lecture_number: int,
                                lecture_name: str, chat_id: int) -> Optional[str]:
        """Download a single lecture file with appropriate naming and preserve original extension."""
        max_retries = 2

        for retry_count in range(max_retries):
            try:
                type_display = lecture_type.capitalize()
                self.bot.send_message(chat_id,
                                      f"📥 Downloading {type_display} {lecture_number}... (Attempt {retry_count + 1})")

                logger.info(f"Download attempt {retry_count + 1} for {safe_name}_{type_prefix}_{lecture_number:02d}")

                # Clear any existing files before starting
                FileManager.cleanup_downloads()

                # Navigate to the lecture URL
                self.selenium.driver.get(url)
                time.sleep(3)

                # Try different methods to trigger download
                downloaded_file = self._trigger_download(chat_id)

                if downloaded_file:
                    # Get the original file extension to preserve DOCX/DOC
                    original_ext = os.path.splitext(downloaded_file)[1].lower()

                    # Generate the filename using the correct lecture number and original extension
                    dst_file = os.path.join(course_folder,
                                            f"{safe_name}_{type_prefix}_{lecture_number:02d}{original_ext}")

                    # Handle file name conflicts
                    counter = 1
                    original_dst_file = dst_file
                    while os.path.exists(dst_file):
                        dst_file = original_dst_file.replace(f"{lecture_number:02d}{original_ext}",
                                                             f"{lecture_number:02d}_{counter}{original_ext}")
                        counter += 1
                        if counter > 10:  # Safety limit
                            timestamp = int(time.time())
                            dst_file = original_dst_file.replace(f"{lecture_number:02d}{original_ext}",
                                                                 f"{lecture_number:02d}_{timestamp}{original_ext}")
                            break

                    shutil.move(downloaded_file, dst_file)
                    file_size_bytes = os.path.getsize(dst_file)
                    file_size_mb = file_size_bytes / (1024 * 1024)  # Convert to MB

                    logger.info(f"Successfully downloaded: {dst_file} ({file_size_mb:.2f} MB)")
                    self.bot.send_message(chat_id, f"✅ Download completed: {file_size_mb:.2f} MB")
                    return dst_file
                else:
                    self.bot.send_message(chat_id, "❌ No file was downloaded")
                    continue

            except Exception as e:
                logger.error(f"Download error on attempt {retry_count + 1}: {e}")
                if retry_count < max_retries - 1:
                    self.bot.send_message(chat_id, "🔄 Retrying download...")
                    time.sleep(3)
                    FileManager.cleanup_downloads()
                else:
                    self.bot.send_message(chat_id, f"❌ Download failed after {max_retries} attempts")

        return None

    def _trigger_download(self, chat_id: int) -> Optional[str]:
        """Try different methods to trigger and detect file download with DOCX/DOC support."""
        # Method 1: Check if there's a direct download link - ADD DOCX/DOC HERE
        try:
            # Look for PDF viewer or direct download links
            download_links = self.selenium.driver.find_elements(By.XPATH,
                                                                "//a[contains(@href, '.pdf') or contains(@href, '.ppt') or contains(@href, '.ppsx') or contains(@href, '.doc') or contains(@href, '.docx')]")
            for link in download_links:
                href = link.get_attribute('href')
                if href and any(ext in href.lower() for ext in ['.pdf', '.ppt', '.pptx', '.ppsx', '.doc', '.docx']):
                    logger.info(f"Found direct download link: {href}")
                    # Click the direct download link
                    link.click()
                    time.sleep(2)
                    break
        except Exception as e:
            logger.debug(f"No direct download links found: {e}")

        # Method 2: Handle iframe content
        try:
            iframe = self.selenium.driver.find_element(By.TAG_NAME, "iframe")
            iframe_src = iframe.get_attribute("src")
            if iframe_src:
                logger.info(f"Found iframe, navigating to: {iframe_src}")
                self.selenium.driver.get(iframe_src)
                time.sleep(2)
        except NoSuchElementException:
            pass

        # Method 3: Try to find and click download buttons
        try:
            download_buttons = self.selenium.driver.find_elements(By.XPATH,
                                                                  "//button[contains(translate(text(), 'DOWNLOAD', 'download'), 'download')] | "
                                                                  "//a[contains(translate(text(), 'DOWNLOAD', 'download'), 'download')] | "
                                                                  "//input[contains(translate(@value, 'DOWNLOAD', 'download'), 'download')]")

            for button in download_buttons:
                try:
                    button.click()
                    time.sleep(2)
                    logger.info("Clicked download button")
                    break
                except:
                    continue
        except Exception as e:
            logger.debug(f"No download buttons found: {e}")

        # Wait for download with progress updates
        self.bot.send_message(chat_id, "⏳ Waiting for download to complete...")

        # Check multiple times with progress - UPDATE EXPECTED EXTENSIONS
        for i in range(500):  # 500 * 2 seconds = 1000 seconds total
            file_path = FileManager.wait_for_file_download_improved(
                expected_exts=(".pdf", ".ppt", ".pptx", ".ptx", ".ppsx", ".doc", ".docx"),
                timeout=2
            )
            if file_path:
                return file_path

            # Send progress update every 20 seconds
            if i % 10 == 0 and i > 0:
                self.bot.send_message(chat_id, f"⏳ Still waiting... ({i * 2} seconds)")

            time.sleep(2)

        return None

    def upload_single_lecture(self, file_path: str, lecture_name: str, chat_id: int,
                              department: str, semester: str, original_name: str,
                              lecture_number: int, lecture_type: str, type_prefix: str) -> bool:
        """Upload a single file to Telegram and update JSON with type information."""
        group_id = GROUP_IDS.get(department)
        if not group_id:
            raise Exception(f"No group ID found for department: {department}")

        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                file_size_bytes = os.path.getsize(file_path)
                file_size_mb = file_size_bytes / (1024 * 1024)  # Convert bytes to MB
                type_display = lecture_type.capitalize()

                # Add this check before attempting upload
                is_ok, check_msg = check_file_size_and_type(file_path)
                # if not is_ok:
                #     self.bot.send_message(chat_id, f"❌ File check failed: {check_msg}")
                #     self.uploaded_files_report["failed"].append(f"{lecture_name} ({check_msg})")
                #     return False

                # Check if file is too large (Telegram has a 50MB limit for bots)
                if file_size_bytes > 50 * 1024 * 1024:  # 45MB safety margin
                    error_msg = f"❌ File too large for Telegram ({file_size_mb:.2f} MB): {lecture_name}"
                    logger.error(error_msg)
                    self.bot.send_message(chat_id, error_msg)
                    return False

                self.bot.send_message(chat_id,
                                      f"📤 Uploading {type_display} {lecture_number} ({file_size_mb:.2f} MB) to Telegram... (Attempt {attempt + 1}/{max_retries})")

                # Increase timeout for larger files
                upload_timeout = max(120, int(file_size_mb * 2))  # At least 2 seconds per MB

                with open(file_path, "rb") as f:
                    # Use a more robust approach for sending files
                    try:
                        sent_msg = self.bot.send_document(
                            group_id,
                            f,
                            caption=os.path.basename(file_path),
                            timeout=upload_timeout,
                            read_timeout=upload_timeout + 30
                        )
                    except Exception as send_error:
                        logger.warning(f"Send document failed: {send_error}, retrying with different approach...")

                        # Retry with simpler parameters
                        f.seek(0)  # Reset file pointer
                        sent_msg = self.bot.send_document(
                            group_id,
                            f,
                            caption=os.path.basename(file_path),
                            timeout=upload_timeout
                        )

                # Create lecture data with type-specific numbering field
                lecture_data = {
                    "message_id": sent_msg.message_id,
                    "file_id": sent_msg.document.file_id,
                    "type": "document",
                    "file_name": os.path.basename(file_path),
                    "lecture_name": lecture_name,
                    "file_size_bytes": file_size_bytes,  # Keep bytes for reference
                    "file_size_mb": round(file_size_mb, 2),  # Add MB with 2 decimal places
                    "lecture_type": lecture_type,
                    "type_prefix": type_prefix,
                    "upload_timestamp": int(time.time())
                }

                # Add type-specific numbering field
                if lecture_type == "tutorial":
                    lecture_data["tutorial_number"] = lecture_number
                elif lecture_type == "assignment":
                    lecture_data["assignment_number"] = lecture_number
                else:  # lecture
                    lecture_data["lecture_number"] = lecture_number

                # Use the DataManager to add lecture while preserving order
                if data_manager.add_lecture_to_json(semester, department, original_name,
                                                    lecture_data, semester_grouped_subjects):

                    if data_manager.save_json(semester_grouped_subjects, SUBJECTS_JSON):
                        self.uploaded_files_report["uploaded"].append(
                            f"{lecture_type} {lecture_number}: {lecture_name}")
                        self.bot.send_message(chat_id,
                                              f"✅ Successfully uploaded: {type_display} {lecture_number} - {lecture_name} ({file_size_mb:.2f} MB)")

                        # Optional: Remove local file after successful upload
                        try:
                            os.remove(file_path)
                            logger.info(f"Cleaned up local file: {file_path}")
                        except Exception as cleanup_error:
                            logger.warning(f"Could not remove local file {file_path}: {cleanup_error}")

                        return True  # Success
                    else:
                        raise Exception("Failed to save JSON data")
                else:
                    raise Exception("Failed to add lecture to JSON data")

            except ConnectionError as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    self.bot.send_message(chat_id, f"📡 Connection issue. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

                    # Try to refresh the bot connection
                    try:
                        self.bot.get_me()
                    except:
                        pass

                    continue
                else:
                    error_msg = f"❌ Upload failed after {max_retries} attempts due to connection issues: {lecture_name}"
                    logger.error(error_msg)
                    self.bot.send_message(chat_id, error_msg)
                    self.uploaded_files_report["failed"].append(f"{lecture_name} (connection error)")
                    return False

            except telebot.apihelper.ApiException as e:
                logger.warning(f"Telegram API error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1) * 2  # Longer wait for API errors
                    self.bot.send_message(chat_id, f"⚡ Telegram API limit. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = f"❌ Upload failed after {max_retries} attempts due to API limits: {lecture_name}"
                    logger.error(error_msg)
                    self.bot.send_message(chat_id, error_msg)
                    self.uploaded_files_report["failed"].append(f"{lecture_name} (API limit)")
                    return False

            except Exception as upload_error:
                logger.error(f"Upload failed on attempt {attempt + 1}: {upload_error}")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    self.bot.send_message(chat_id, f"🔄 Upload failed. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = f"❌ Upload failed after {max_retries} attempts: {lecture_name} - {str(upload_error)}"
                    logger.error(error_msg)
                    self.bot.send_message(chat_id, error_msg)
                    self.uploaded_files_report["failed"].append(f"{lecture_name} ({str(upload_error)})")
                    return False

        return False


# ------------------- SCP UPLOAD FUNCTIONS -------------------
def upload_json_to_server():
    """Upload the JSON file to Linux server via SCP and restart the bot service."""
    try:
        logger.info("Starting SCP upload to server...")

        with ssh_connection() as ssh:
            # Upload JSON file via SCP
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(SUBJECTS_JSON, SERVER_CONFIG['remote_json_path'])
                logger.info(f"JSON file uploaded to {SERVER_CONFIG['remote_json_path']}")

            # Use interactive shell for sudo
            shell = ssh.invoke_shell()
            shell.settimeout(10)

            # Send commands
            commands = [
                f"cd {SERVER_CONFIG['remote_script_path']}",
                f"sudo systemctl restart telegrambot",
                SERVER_CONFIG['password'],  # Password input
                "sleep 2",
                "sudo systemctl status telegrambot --no-pager"
            ]

            output = ""
            for command in commands:
                shell.send(command + '\n')
                time.sleep(2)

                # Read output
                while shell.recv_ready():
                    output += shell.recv(1024).decode('utf-8')

            shell.close()

            if "active (running)" in output:
                logger.info("✅ Server bot service restarted successfully")
                return "✅ JSON uploaded and server bot restarted successfully"
            else:
                logger.error(f"❌ Server restart failed. Output: {output}")
                return "❌ Server restart failed. Check service status."

    except Exception as e:
        logger.error(f"SCP upload failed: {e}")
        return f"❌ SCP upload failed: {str(e)}"


def test_server_connection():
    """Test connection to the server."""
    try:
        with ssh_connection() as ssh:
            return True, "✅ Server connection successful"
    except Exception as e:
        return False, f"❌ Server connection failed: {str(e)}"


# ------------------- UPLOAD FLOW -------------------
def start_upload_flow_async(chat_id: int, auto_upload: bool = False):
    """Main upload flow - process one subject at a time."""
    data_manager.backup_json_files()
    selenium_manager = None

    try:
        # Get user settings
        user_setting = user_settings.get(str(chat_id), {})
        semester = user_setting.get("semester")
        department = user_setting.get("department")

        logger.info(f"User settings: semester={semester}, department={department}")

        if not semester or not department:
            bot.send_message(chat_id, "⚠️ Please set semester and department using /settings first")
            return

        # Initialize Selenium
        try:
            bot.send_message(chat_id, "🔄 Initializing browser session...")
            selenium_manager = SeleniumManager()
            bot.send_message(chat_id, "✅ Browser session initialized")
        except Exception as e:
            error_msg = f"❌ Failed to initialize browser: {str(e)}"
            logger.error(error_msg)
            bot.send_message(chat_id, error_msg)
            return

        # Initialize download manager
        download_manager = DownloadManager(bot, selenium_manager)

        # Reset report
        download_manager.uploaded_files_report.clear()
        download_manager.uploaded_files_report.update(
            {"uploaded": [], "skipped": [], "failed": [], "recovered": []})

        bot.send_message(chat_id, f"🔄 Starting upload process for {department} - {semester}...")
        logger.info(f"Starting upload for user {chat_id}, semester {semester}, department {department}")

        # Collect all courses
        course_manager = CourseManager(selenium_manager)
        bot.send_message(chat_id, "🔍 Scanning for courses...")
        all_courses = course_manager.collect_courses()

        if not all_courses:
            bot.send_message(chat_id, "⚠️ No courses found on dashboard.")
            return

        bot.send_message(chat_id, f"📚 Found {len(all_courses)} courses. Processing sequentially...")

        # Process courses one by one
        download_manager.process_course_sequentially(all_courses, chat_id, department, semester)

        # Send final report
        send_upload_report(chat_id, download_manager.uploaded_files_report)

        # Auto-upload to server if requested
        if auto_upload:
            bot.send_message(chat_id, "🔄 Uploading JSON to server...")
            upload_result = upload_json_to_server()
            bot.send_message(chat_id, upload_result)

    except Exception as e:
        error_msg = f"❌ Upload process failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            bot.send_message(chat_id, f"❌ {error_msg}")
        except:
            pass
    finally:
        # Ensure Selenium manager is properly closed
        if selenium_manager:
            try:
                selenium_manager.quit()
                logger.info("Selenium manager cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up selenium manager: {e}")


def check_file_size_and_type(file_path: str) -> Tuple[bool, str]:
    """Check if file is suitable for Telegram upload."""
    try:
        if not os.path.exists(file_path):
            return False, "File does not exist"

        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()

        # Telegram bot file size limit is 50MB
        if file_size > 50 * 1024 * 1024:
            return False, f"File too large ({file_size / (1024 * 1024):.2f} MB > 50 MB limit)"

        # Check if file is empty or too small
        if file_size < 100:  # 100 bytes minimum
            return False, "File too small or empty"

        # Check if file extension is supported
        supported_extensions = ['.pdf', '.ppt', '.pptx', '.doc', '.docx', '.ppsx', '.ptx']
        if file_ext not in supported_extensions:
            return False, f"Unsupported file extension: {file_ext}"

        return True, f"File OK ({file_size / (1024 * 1024):.2f} MB)"

    except Exception as e:
        return False, f"Error checking file: {str(e)}"


def send_upload_report(chat_id: int, report: Dict):
    """Send comprehensive upload report with better formatting."""
    try:
        report_lines = [
            "📊 *Upload Process Completed*",
            "",
            f"✅ *Uploaded:* {len(report['uploaded'])}",
            f"⏭️ *Skipped:* {len(report['skipped'])}",
            f"❌ *Failed:* {len(report['failed'])}",
            f"🔧 *Recovered:* {len(report.get('recovered', []))}",
            ""
        ]

        # Show some uploaded files (max 5)
        if report["uploaded"]:
            report_lines.append("*Recently Uploaded:*")
            for name in report["uploaded"][-5:]:  # Last 5 items
                report_lines.append(f"  • {name}")
            report_lines.append("")

        # Show failed files if any
        if report["failed"]:
            report_lines.append("*Failed Files:*")
            for name in report["failed"][:3]:  # First 3 failures
                report_lines.append(f"  • {name}")
            if len(report["failed"]) > 3:
                report_lines.append(f"  ... and {len(report['failed']) - 3} more")
            report_lines.append("")

        report_text = "\n".join(report_lines)
        bot.send_message(chat_id, report_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error sending report: {e}")
        # Fallback simple report
        simple_report = (
            f"📊 Upload Complete:\n"
            f"✅ Uploaded: {len(report['uploaded'])}\n"
            f"⏭️ Skipped: {len(report['skipped'])}\n"
            f"❌ Failed: {len(report['failed'])}"
        )
        bot.send_message(chat_id, simple_report)


def recover_missing_files(missing_files: List[Tuple], chat_id: int, department: str, semester: str,
                          course_manager: CourseManager, download_manager: DownloadManager):
    """Recover files that are in JSON but missing from disk."""
    if not missing_files:
        bot.send_message(chat_id, "✅ No missing files found for this department.")
        return

    all_courses = course_manager.collect_courses()
    if not all_courses:
        bot.send_message(chat_id, "⚠️ No courses found on dashboard.")
        return

    recovered_count = 0

    for original_name, filename in missing_files:
        bot.send_message(chat_id, f"🔄 Recovering: {filename}")

        # Find matching course
        course_found = False
        for course_name, course_url in all_courses.items():
            _, course_original_name = FileManager.clean_subject_name(course_name)
            if course_original_name == original_name:
                lectures = course_manager.collect_lectures(course_url)
                course_folder = os.path.join(DOWNLOAD_DIR, original_name)
                safe_name, _ = FileManager.clean_subject_name(original_name)

                # Extract lecture number from missing filename
                match = re.search(rf"{re.escape(safe_name)}_lec_(\d+)", filename)
                if match:
                    lecture_number = int(match.group(1))
                    lecture_items = list(lectures.items())
                    if lecture_number <= len(lecture_items):
                        lecture_id, lecture_data = lecture_items[lecture_number - 1]
                        task = (course_folder, lecture_data, lecture_number, safe_name, chat_id, department, semester,
                                original_name)
                        download_manager.download_queue.put(task)
                        recovered_count += 1
                        bot.send_message(chat_id, f"🔄 Recovering lec{lecture_number}: {lecture_data['name']}")
                course_found = True
                break

        if not course_found:
            bot.send_message(chat_id, f"❌ Course not found: {original_name}")

    if recovered_count == 0:
        bot.send_message(chat_id, "❌ No files could be recovered")


def process_courses(courses: Dict[str, str], chat_id: int, department: str, semester: str,
                    course_manager: CourseManager, download_manager: DownloadManager):
    """Process all courses for uploading."""
    bot.send_message(chat_id, f"📚 Processing {len(courses)} courses...")

    for course_name, course_url in courses.items():
        safe_name, original_name = FileManager.clean_subject_name(course_name)
        bot.send_message(chat_id, f"📖 Processing: {original_name}")

        lectures = course_manager.collect_lectures(course_url)
        if not lectures:
            bot.send_message(chat_id, f"⚠️ No lectures found for: {original_name}")
            continue

        course_folder = os.path.join(DOWNLOAD_DIR, original_name)
        process_lectures(lectures, course_folder, safe_name, chat_id, department, semester, original_name,
                         download_manager)


def process_lectures(lectures: Dict, course_folder: str, safe_name: str, chat_id: int,
                     department: str, semester: str, original_name: str, download_manager: DownloadManager):
    """Process lectures for a course maintaining original numbering."""
    existing_files_info = semester_grouped_subjects.get(semester, {}).get(department, {}).get(original_name, [])

    # Create sets of existing lecture numbers and names
    existing_lecture_numbers = set()
    existing_lecture_names = set()

    for file_info in existing_files_info:
        match = re.search(rf"{re.escape(safe_name)}_lec_(\d+)", file_info["file_name"])
        if match:
            lecture_num = int(match.group(1))
            existing_lecture_numbers.add(lecture_num)
        existing_lecture_names.add(file_info["lecture_name"])

    # Process lectures in their original order
    for lecture_number, (lecture_id, lecture_data) in enumerate(lectures.items(), 1):
        if lecture_number in existing_lecture_numbers or lecture_data["name"] in existing_lecture_names:
            download_manager.uploaded_files_report["skipped"].append(lecture_data["name"])
            bot.send_message(chat_id, f"⏭️ Skipped lec{lecture_number}: {lecture_data['name']}")
        else:
            task = (course_folder, lecture_data, lecture_number, safe_name, chat_id, department, semester,
                    original_name)
            download_manager.download_queue.put(task)
            bot.send_message(chat_id, f"📥 Queued lec{lecture_number}: {lecture_data['name']}")


def send_upload_report(chat_id: int, report: Dict):
    """Send comprehensive upload report."""
    report_lines = ["📊 Upload Process Completed", ""]

    if report["uploaded"]:
        report_lines.append(f"✅ Uploaded ({len(report['uploaded'])}):")
        report_lines.extend([f"  • {name}" for name in report["uploaded"][:10]])
        if len(report["uploaded"]) > 10:
            report_lines.append(f"  ... and {len(report['uploaded']) - 10} more")
        report_lines.append("")

    if report["recovered"]:
        report_lines.append(f"🔧 Recovered ({len(report['recovered'])}):")
        report_lines.extend([f"  • {name}" for name in report["recovered"][:5]])
        report_lines.append("")

    if report["skipped"]:
        report_lines.append(f"⏭️ Skipped ({len(report['skipped'])}):")
        report_lines.append("")

    if report["failed"]:
        report_lines.append(f"❌ Failed ({len(report['failed'])}):")
        report_lines.extend([f"  • {name}" for name in report["failed"][:5]])
        report_lines.append("")

    report_text = "\n".join(report_lines)
    bot.send_message(chat_id, report_text)


# ------------------- INTEGRITY CHECK -------------------
def check_folder_integrity(department: str, semester: str) -> List[Tuple[str, str]]:
    """Check if files referenced in JSON actually exist on disk."""
    missing_files = []

    if not semester_grouped_subjects:
        logger.info("JSON data is empty - no subjects to check")
        return missing_files

    if semester not in semester_grouped_subjects or department not in semester_grouped_subjects[semester]:
        logger.info(f"Department {department} not found in semester {semester}")
        return missing_files

    subjects = semester_grouped_subjects[semester][department]

    # ✅ ADDED: Check if subjects is empty or None
    if not subjects:
        logger.info(f"No subjects found for {department} - {semester} (empty department)")
        return missing_files

    for original_name, files in subjects.items():
        if not files:
            continue

        course_folder = os.path.join(DOWNLOAD_DIR, original_name)

        if not os.path.exists(course_folder):
            logger.warning(f"Folder doesn't exist: {course_folder}")
            for file_info in files:
                if file_info.get("file_name"):
                    missing_files.append((original_name, file_info["file_name"]))
            continue

        for file_info in files:
            file_name = file_info.get("file_name")
            if not file_name:
                continue

            expected_path = os.path.join(course_folder, file_name)
            if not os.path.exists(expected_path):
                logger.warning(f"File missing: {expected_path}")
                missing_files.append((original_name, file_name))

    logger.info(f"Integrity check for {department}-{semester}: {len(missing_files)} missing files")
    return missing_files


# ------------------- TELEGRAM HANDLERS -------------------
def save_settings():
    """Save user settings to file."""
    data_manager.save_json(user_settings, SETTINGS_FILE)


@bot.message_handler(commands=["auto_upload"])
def auto_upload_command(message):
    """Handle auto upload command with SCP transfer."""
    if message.chat.id not in ADMIN_CHAT_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    bot.reply_to(message, "🚀 Starting upload process with auto server sync...")
    threading.Thread(target=start_upload_flow_async, args=(message.chat.id, True), daemon=True).start()


@bot.message_handler(commands=["test_server"])
def test_server_command(message):
    """Test server connection."""
    if message.chat.id not in ADMIN_CHAT_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    success, result = test_server_connection()
    bot.reply_to(message, result)


@bot.message_handler(commands=["upload_json"])
def upload_json_command(message):
    """Upload JSON to server without doing full upload process."""
    if message.chat.id not in ADMIN_CHAT_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    bot.reply_to(message, "🔄 Uploading JSON to server...")
    result = upload_json_to_server()
    bot.reply_to(message, result)


@bot.message_handler(commands=["upload"])
def upload_command(message):
    """Handle upload command."""
    if message.chat.id not in ADMIN_CHAT_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    chat_id = message.chat.id
    print(chat_id)
    bot.reply_to(message, "🚀 Starting upload process in background...")
    threading.Thread(target=start_upload_flow_async, args=(chat_id, False), daemon=True).start()


@bot.message_handler(commands=["debug_selenium"])
def debug_selenium_command(message):
    """Debug Selenium initialization."""
    if message.chat.id not in ADMIN_CHAT_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        bot.reply_to(message, "🔄 Testing Selenium initialization...")

        # Test driver setup
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://www.google.com")

        status = f"✅ Selenium test passed! Page title: {driver.title}"
        driver.quit()

    except Exception as e:
        status = f"❌ Selenium test failed: {str(e)}"

    bot.reply_to(message, status)


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    """Send welcome message and available commands."""
    welcome_text = """
🤖 *Elearning Bot Help*

*Available Commands:*

📤 *Upload Commands:*
/upload - Start upload process
/auto_upload - Upload with auto server sync
/preview_changes - Preview course naming before upload

⚙️ *Settings & Management:*
/settings - Configure semester and department
/upload_json - Upload JSON to server only
/test_server - Test server connection

🔧 *Technical:*
/debug_selenium - Test Selenium setup

*Admin Only Commands:*
All upload and management commands are admin-only.

*How to use:*
1. First, set your semester and department using /settings
2. Use /preview_changes to see how courses will be named
3. Use /upload to start the upload process
    """
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=["settings"])
def settings_command(message):
    """Handle settings configuration."""
    chat_id = message.chat.id

    # Create settings keyboard
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Semester buttons
    markup.add(
        InlineKeyboardButton("Semester 7", callback_data="settings_semester_7"),
        InlineKeyboardButton("Semester 8", callback_data="settings_semester_8")
    )

    # Department buttons
    departments = [
        ("Electronics", "electronics"),
        ("Mechatronics", "mechatronics"),
        ("Biomedical", "biomedical"),
        ("Computer", "computer"),
        ("TCOM", "tcom"),
        ("Linux", "linux")
    ]

    for dept_name, dept_code in departments:
        markup.add(InlineKeyboardButton(dept_name, callback_data=f"settings_department_{dept_code}"))

    # Load current settings
    current_settings = user_settings.get(str(chat_id), {})
    current_semester = current_settings.get("semester", "Not set")
    current_department = current_settings.get("department", "Not set")

    settings_text = f"""
⚙️ *Current Settings:*
• Semester: `{current_semester}`
• Department: `{current_department}`

*Select your settings below:*
    """

    bot.send_message(chat_id, settings_text, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith('settings_'))
def handle_settings_callback(call):
    """Handle settings callback queries."""
    chat_id = call.message.chat.id
    data = call.data

    if data.startswith('settings_semester_'):
        semester = data.replace('settings_semester_', '')
        if str(chat_id) not in user_settings:
            user_settings[str(chat_id)] = {}
        user_settings[str(chat_id)]["semester"] = semester
        save_settings()

        bot.answer_callback_query(call.id, f"Semester {semester} set!")
        update_settings_message(call.message, chat_id)

    elif data.startswith('settings_department_'):
        department = data.replace('settings_department_', '')
        if str(chat_id) not in user_settings:
            user_settings[str(chat_id)] = {}
        user_settings[str(chat_id)]["department"] = department
        save_settings()

        bot.answer_callback_query(call.id, f"Department {department} set!")
        update_settings_message(call.message, chat_id)


def update_settings_message(message, chat_id):
    """Update the settings message with current values."""
    current_settings = user_settings.get(str(chat_id), {})
    current_semester = current_settings.get("semester", "Not set")
    current_department = current_settings.get("department", "Not set")

    updated_text = f"""
⚙️ *Settings Updated!*

*Current Settings:*
• Semester: `{current_semester}`
• Department: `{current_department}`

You can now use /upload to start the process.
    """

    bot.edit_message_text(
        updated_text,
        chat_id=chat_id,
        message_id=message.message_id,
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["recover_json"])
def recover_json_command(message):
    """Emergency JSON recovery command."""
    if message.chat.id not in ADMIN_CHAT_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        bot.reply_to(message, "🔄 Attempting JSON recovery...")

        # Check for backups
        backup_files = glob.glob("semester_subjects.json.backup*")
        if not backup_files:
            bot.reply_to(message, "❌ No backup files found.")
            return

        # Show available backups
        backup_info = []
        for i, backup in enumerate(backup_files[-10:]):  # Show last 10 backups
            mtime = os.path.getmtime(backup)
            date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            size_kb = os.path.getsize(backup) / 1024
            backup_info.append(f"{i + 1}. {date_str} - {size_kb:.1f} KB - {os.path.basename(backup)}")

        markup = types.InlineKeyboardMarkup()
        for i, backup in enumerate(backup_files[-5:]):  # Offer last 5 for recovery
            markup.add(InlineKeyboardButton(f"Recovery {i + 1}", callback_data=f"recover_{i}"))

        message_text = "📂 Available backups:\n" + "\n".join(backup_info[-10:])
        bot.send_message(message.chat.id, message_text, reply_markup=markup)

    except Exception as e:
        bot.reply_to(message, f"❌ Recovery failed: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('recover_'))
def handle_recovery_callback(call):
    """Handle recovery callback."""
    chat_id = call.message.chat.id
    backup_index = int(call.data.replace('recover_', ''))

    try:
        backup_files = glob.glob("semester_subjects.json.backup*")
        backup_files.sort(key=os.path.getctime)

        if 0 <= backup_index < len(backup_files):
            selected_backup = backup_files[backup_index]

            # Restore the backup
            with open(selected_backup, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            with open(SUBJECTS_JSON, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            # Reload the global variable
            global semester_grouped_subjects
            semester_grouped_subjects = data_manager.load_json_or_default(SUBJECTS_JSON, {})

            bot.answer_callback_query(call.id, f"✅ Restored from {os.path.basename(selected_backup)}")
            bot.send_message(chat_id,
                             f"✅ Successfully restored JSON from backup!\nFile: {os.path.basename(selected_backup)}")
        else:
            bot.answer_callback_query(call.id, "❌ Invalid backup selection")

    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Recovery failed")
        bot.send_message(chat_id, f"❌ Recovery error: {e}")


@bot.message_handler(commands=["dashboard"])
def dash_board(message, user_id=None):
    chat_id = user_id if user_id else message.chat.id
    if chat_id in ADMIN_CHAT_IDS:
        settings_data = user_settings.get(str(chat_id), {})
        semester: str = settings_data.get("semester", "N/A")
        department: str = settings_data.get("department", "N/A")
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
            summary_lines.append(f"... and {len(course_sizes) - 11} more courses")

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


# ------------------- MAIN EXECUTION -------------------
def main():
    """Main application entry point."""
    try:
        logger.info("Starting Elearning Bot")
        print("🤖 Bot started. Waiting for commands...")

        # Validate JSON data on startup
        issues = data_manager.validate_json_data(semester_grouped_subjects)
        if issues > 0:
            logger.info(f"Fixed {issues} JSON validation issues on startup")

        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")
    finally:
        # Cleanup is now handled by context managers
        pass


if __name__ == "__main__":
    stop_server_bot()
    main()
