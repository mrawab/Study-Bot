import os
import time
import re
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
load_dotenv()

# --- SETTINGS ---
DOWNLOAD_DIR = r"D:\ElearningDownloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

USERNAME = os.getenv("ELEARNING_USERNAME")
PASSWORD = os.getenv("ELEARNING_PASSWORD")

# --- CHROME OPTIONS ---
chrome_options = Options()
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "plugins.always_open_pdf_externally": True
})
# chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# --- START BROWSER ---
driver = webdriver.Chrome(options=chrome_options)
driver.get("https://elearning.fu.edu.sd/login/index.php")

# --- LOGIN ---
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username"))).send_keys(USERNAME)
driver.find_element(By.ID, "password").send_keys(PASSWORD)
driver.find_element(By.ID, "loginbtn").click()
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h4")))

# --- COLLECT COURSES ---
def collect_courses():
    courses = {}
    course_links = driver.find_elements(By.CSS_SELECTOR, "h4.card-title a")
    for link in course_links:
        name = link.text.strip()
        url = link.get_attribute("href")
        courses[name] = url
    return courses

# --- CHECK IF FILE EXISTS ---
def is_file_already_downloaded(course_folder, lecture_name):
    if not os.path.exists(course_folder):
        return False
    for f in os.listdir(course_folder):
        name, ext = os.path.splitext(f)
        if name == lecture_name:
            return True
    return False

# --- COLLECT LECTURES ---
def collect_lectures(course_name, courses):
    lectures = {}
    driver.get(courses[course_name])
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.activityinstance a.aalink"))
    )

    lecture_links = driver.find_elements(By.CSS_SELECTOR, "div.activityinstance a.aalink")
    lec_counter = 1
    for link in lecture_links:
        name = link.find_element(By.CSS_SELECTOR, "span.instancename").text.strip()
        name = name.replace("File", "").replace("Quiz", "").replace("External tool", "").strip()
        img = link.find_element(By.TAG_NAME, "img")
        img_src = img.get_attribute("src").lower()

        if any(x in name.lower() for x in ["midterm", "final", "quiz", "smowl"]):
            continue
        elif "mp3" in img_src:
            print(f"⏩ Skipping audio: {link.text.strip()}")
            continue
        elif not ("pdf" in img_src or "pptx" in img_src or "powerpoint" in img_src):
            print(f"⏩ Skipping non-PDF/PPTX: {link.text.strip()}")
            continue

        safe_name = re.sub(r'[\\/*?:"<>|]', "", course_name)
        lectures[f"{safe_name}_Lec{lec_counter}"] = link.get_attribute("href")
        lec_counter += 1
    return lectures

# --- DOWNLOAD LECTURE ---
def download_lecture(course_folder, lecture_name, url):
    if is_file_already_downloaded(course_folder, lecture_name):
        print(f"⏩ Already downloaded: {lecture_name}")
        return

    print(f"\nProcessing: {lecture_name}")
    os.makedirs(course_folder, exist_ok=True)

    try:
        driver.get(url)
        time.sleep(0.5)

        # Handle iframe PDFs
        try:
            iframe = driver.find_element(By.TAG_NAME, "iframe")
            driver.get(iframe.get_attribute("src"))
            time.sleep(0.5)
        except:
            pass

        print(f"✅ Download started for: {lecture_name}")

        # --- WATCHDOG FOR .crdownload ---
        timeout = 300
        elapsed = 0
        poll_interval = 1
        downloaded_file = None

        while elapsed < timeout:
            cr_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith(".crdownload")]
            if cr_files:
                downloaded_file = cr_files[0]
                break
            time.sleep(poll_interval)
            elapsed += poll_interval

        if not downloaded_file:
            print(f"⚠️ No download started for {lecture_name}")
            return

        cr_file_path = os.path.join(DOWNLOAD_DIR, downloaded_file)
        elapsed = 0
        while os.path.exists(cr_file_path) and elapsed < timeout:
            time.sleep(1)
            elapsed += 1

        if elapsed >= timeout:
            print(f"⚠️ Timeout waiting for {lecture_name}")
            return

        # --- MOVE FINISHED FILE ---
        files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
        if not files:
            print(f"⚠️ No file found for {lecture_name}")
            return

        final_file = max(files, key=os.path.getctime)
        if os.path.getsize(final_file) < 50 * 1024:
            print(f"⚠️ File too small, might be error page: {lecture_name}")
            return

        ext = os.path.splitext(final_file)[1]
        dst_path = os.path.join(course_folder, f"{lecture_name}{ext}")
        shutil.move(final_file, dst_path)
        print(f"✅ File saved: {dst_path}")

    except Exception as e:
        print(f"❌ Error processing {lecture_name}: {e}")

# --- DOWNLOAD COURSE ---
def download_course(course_name, course_url):
    safe_course_name = re.sub(r'[\\/*?:"<>|]', "", course_name)
    course_folder = os.path.join(DOWNLOAD_DIR, safe_course_name)

    print(f"\nDownloading lectures for: {course_name}")
    lectures = collect_lectures(course_name, courses)

    for name, url in lectures.items():
        download_lecture(course_folder, name, url)

    print(f"\n✅ Finished all lectures for: {course_name}")

# --- MAIN LOOP ---
while True:
    time.sleep(1)
    courses = collect_courses()
    print("\nAvailable Courses:\n")
    for i, (name, url) in enumerate(courses.items(), start=1):
        print(f"{i}. {name}")

    choice = input("\nEnter course number to download (or 'all' for everything, 'q' to quit): ")

    if choice.lower() == "q":
        print("\nExiting program...")
        break

    if choice.lower() == "all":
        for course_name, course_url in courses.items():
            download_course(course_name, course_url)
        print("\n✅ Finished downloading all courses!")
        driver.get("https://elearning.fu.edu.sd/")
        time.sleep(3)
        continue

    try:
        choice = int(choice)
        course_name = list(courses.keys())[choice - 1]
        download_course(course_name, courses[course_name])
        driver.back()
        time.sleep(2)

    except (ValueError, IndexError):
        print("❌ Invalid choice. Try again.")

print("Browser remains open. Close it manually when ready.")
