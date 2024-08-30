import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import sympy as sp
import json
import os
import requests
import io
import contextlib
import ast
import atexit
import threading
import time
import nbformat
from nbformat import v4 as nbf
import pdf2image
from io import BytesIO
from PIL import Image
from gtts import gTTS
import zipfile
from moviepy.editor import VideoFileClip
import speech_recognition as sr
import re
from pytube import YouTube

bot = telebot.TeleBot('TELEGRAM_BOT_API')
UNSPLASH_ACCESS_KEY = 'UNSPLASH_ACCESS_KEY'
ADMIN_CHAT_ID = 'YOUR_ADMIN_CHAT_ID'
subjects_url = "YOUR_SUBJECTS_URL_JSON"
SUBSCRIBERS_FILE =
"YOUR_SUBSCRIBERS_JSON"
user_states = {}
subjects_json = "YOUR_SUBJECTS_JSON"
subject_file = "YOUR_SUBJECTS_FILE_DIR"



# Load subjects from JSON file
if os.path.exists(subjects_json):
    with open(subjects_json, 'r') as f:
        subject_pdfs = json.load(f)
else:
    subject_pdfs = {}
    

@bot.message_handler(commands=['lecture'])
def request_code(message):
    bot.reply_to(message, "Please enter the code for your department:")
    bot.send_message(message.chat.id, "3030 for Electronics batch\n4040 for Mechatronics batch")
    bot.register_next_step_handler(message, verify_code)

def verify_code(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return

    code = message.text.strip()

    if code == "3030":
        bot.send_message(message.chat.id, "Electronics batch")
        send_pdf_list(message, "electronics")
    elif code == "4040":
        bot.send_message(message.chat.id, "Mechatronics batch")
        send_pdf_list(message, "mechatronics")
    else:
        bot.reply_to(message, "Invalid code. Please enter a valid code.")

def send_pdf_list(message, department):
    if department not in subject_pdfs:
        bot.send_message(
            message.chat.id,
            "No subjects available for this department at the moment. Please try again later.")
        return

    markup = InlineKeyboardMarkup()
    for subject in subject_pdfs[department].keys():
        # Simplified callback data to avoid issues
        callback_data = f"pdf_{department}_{subject.replace(' ', '_')}"
        markup.add(
            InlineKeyboardButton(subject, callback_data=callback_data))

    bot.reply_to(message,
                 "Choose a subject to download the PDFs:",
                 reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pdf_'))
def handle_pdf_download(call):
    data = call.data.split('_')
    department = data[1]
    subject = ' '.join(data[2:]).replace('_', ' ')

    if department in subject_pdfs and subject in subject_pdfs[department]:
        pdf_list = subject_pdfs[department][subject]
        if not pdf_list:
            bot.send_message(call.message.chat.id, f"No PDFs available for {subject} at the moment.")
            return

        markup = InlineKeyboardMarkup()
        for i, pdf in enumerate(pdf_list):
            callback_data = f"download_{department}_{subject.replace(' ', '_')}_{i}"
            markup.add(InlineKeyboardButton(f"Lecture {i+1}", callback_data=callback_data))

        markup.add(InlineKeyboardButton("Download all as ZIP", callback_data=f"download_zip_{department}_{subject.replace(' ', '_')}"))
        bot.send_message(call.message.chat.id, f"Choose a PDF to download for {subject}:", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, f"Sorry, no PDFs available for {subject} yet.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
def download_selected_pdf(call):
    try:
        data = call.data.split('_')
        action = data[3]
        action_zip = data[1]
        department_zip = data[2]
        department = data[1]
        subject = ''

        if action_zip == 'zip':
            subject = ' '.join(data[3:]).replace('_', ' ')  # Get the subject name from remaining data
            # Debugging print statements
            print(f"Action: {action_zip}")
            print(f"Department: {department_zip}")
            print(f"Subject: {subject}")

            if subject in subject_pdfs.get(department_zip, {}):
                pdf_list = subject_pdfs[department_zip][subject]
                if pdf_list:
                    zip_filename = f"{subject.replace(' ', '_')}.zip"
                    with zipfile.ZipFile(zip_filename, 'w') as zipf:
                        for pdf_path in pdf_list:
                            zipf.write(pdf_path, os.path.basename(pdf_path))
                    with open(zip_filename, 'rb') as zip_file:
                        bot.send_document(call.message.chat.id, zip_file)
                    os.remove(zip_filename)
                else:
                    bot.send_message(call.message.chat.id, f"No PDFs available to download as ZIP for {subject}.")
            else:
                bot.send_message(call.message.chat.id, f"Subject '{subject}' not found in department '{department}'.")
        else:  # Handle individual PDF download
            try:
                pdf_index = int(data[-1])  # Convert the index from string to int
                subject = ' '.join(data[2:-1]).replace('_', ' ')  # Extract subject from data

                # Debugging print statements
                print(f"Action: {action}")
                print(f"Department: {department}")
                print(f"Subject: {subject}")
                print(f"PDF Index: {pdf_index}")

                if subject in subject_pdfs.get(department, {}):
                    pdf_list = subject_pdfs[department][subject]
                    if 0 <= pdf_index < len(pdf_list):
                        pdf_path = pdf_list[pdf_index]
                        try:
                            with open(pdf_path, 'rb') as pdf_file:
                                bot.send_document(call.message.chat.id, pdf_file)
                        except FileNotFoundError:
                            bot.send_message(call.message.chat.id, f"Sorry, the PDF for {subject} is not available.")
                        except Exception as e:
                            bot.send_message(call.message.chat.id, f"An error occurred while processing your request: {e}")
                    else:
                        bot.send_message(call.message.chat.id, f"No valid PDF found for {subject}.")
                else:
                    bot.send_message(call.message.chat.id, f"Subject '{subject}' not found in department '{department}'.")
            except ValueError:
                bot.send_message(call.message.chat.id, "Invalid PDF index provided.")
                return
    except Exception as e:
        bot.send_message(call.message.chat.id, f"An unexpected error occurred: {e}")
        print(f"Error in callback handler: {e}")


@bot.message_handler(commands=['upload'])
def request_upload_code(message):
    if message.chat.id == ADMIN_CHAT_ID:
    	bot.reply_to(message, "Please enter the code for your department to upload the PDF:")
    	bot.register_next_step_handler(message, process_upload_code)
    else:
    	bot.send_message(message.chat.id,"unauthorized access to upload")

def process_upload_code(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return

    code = message.text.strip()

    if code == "3030":
        department = "electronics"
    elif code == "4040":
        department = "mechatronics"
    else:
        bot.reply_to(message, "Invalid code. Please enter a valid code.")
        return

    bot.reply_to(message, f"Department: {department}. Please enter the subject name:")
    bot.register_next_step_handler(message, process_subject_name, department)

def process_subject_name(message, department):
    if message.text.lower() == "/cancel":
        cancel(message)
        return

    subject_name = message.text.strip()

    bot.reply_to(message, f"Subject: {subject_name}. Please upload the PDF file:")
    bot.register_next_step_handler(message, process_pdf_upload, department, subject_name)

def process_pdf_upload(message, department, subject_name):
    if message.document and message.document.mime_type == 'application/pdf':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        subject_dir = os.path.join(subject_file)
        os.makedirs(subject_dir, exist_ok=True)
        pdf_file_path = os.path.join(subject_dir, message.document.file_name)

        with open(pdf_file_path, 'wb') as pdf_file:
            pdf_file.write(downloaded_file)

        # Update the JSON file with the new PDF
        if department not in subject_pdfs:
            subject_pdfs[department] = {}
        if subject_name not in subject_pdfs[department]:
            subject_pdfs[department][subject_name] = []
        subject_pdfs[department][subject_name].append(pdf_file_path)

        with open(subjects_json, 'w') as f:
            json.dump(subject_pdfs, f, indent=4)

        bot.reply_to(message, f"PDF uploaded successfully to {subject_name} under {department}.")
    else:
        bot.reply_to(message, "Invalid file format. Please upload a PDF file.")


@bot.message_handler(commands=['transcript'])
def ask_for_video(message):
    bot.reply_to(message, "Please send the video file which you want to extract the transcript.")
    bot.register_next_step_handler(message, extract_transcript)

def extract_transcript(message):
    if message.text and message.text.lower() == "/cancel":
        cancel(message)
        return

    video_file_path = None
    file_info = None

    youtube_url_pattern = re.compile(
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    if message.video:  # If the video is sent as a video file
        file_info = bot.get_file(message.video.file_id)
        video_file_path = message.video.file_name
    elif message.document and message.document.mime_type.startswith('video/'):  # If the video is sent as a document
        file_info = bot.get_file(message.document.file_id)
        video_file_path = message.document.file_name
    elif message.text and youtube_url_pattern.match(message.text):  # If the video is sent as a YouTube link
        youtube_url = message.text
        yt = YouTube(youtube_url)
        stream = yt.streams.filter(only_audio=False, file_extension='mp4').first()
        video_file_path = 'downloaded_video.mp4'
        stream.download(filename=video_file_path)

    if (file_info and video_file_path) or (not file_info and youtube_url):
        if file_info:  # If the video was sent as a file
            downloaded_file = bot.download_file(file_info.file_path)
            with open(video_file_path, 'wb') as video_file:
                video_file.write(downloaded_file)

        # Extract audio from video
        video = VideoFileClip(video_file_path)
        audio_file_path = video_file_path.replace('.mp4', '.wav')
        video.audio.write_audiofile(audio_file_path)

        # Transcribe audio to text
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_file_path) as source:
            audio_data = recognizer.record(source)
            try:
                transcript = recognizer.recognize_google(audio_data)
                bot.reply_to(message, f"Transcript:\n{transcript}")
            except sr.UnknownValueError:
                bot.reply_to(message, "Sorry, could not understand the audio.")
            except sr.RequestError:
                bot.reply_to(message, "Sorry, there was an error with the request.")
        os.remove(video_file_path)
        os.remove(audio_file_path)

    else:
        bot.reply_to(message, "Please send a valid video file.")



@bot.message_handler(commands=['report'])
def report_issue(message):
    bot.reply_to(message, "Please describe the issue you're facing:")
    bot.register_next_step_handler(message, handle_report)
    save_subscribers()

def handle_report(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return
    # Construct the clickable link using Telegram markdown
    report_text = f"Report from user <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name} {message.from_user.last_name}</a> : \n\n{message.text}"
    bot.send_message(ADMIN_CHAT_ID, report_text, parse_mode='HTML')
    bot.reply_to(message, "Thank you for your report! We'll look into it.")

@bot.message_handler(commands=['count'])
def count(message):
  if message.chat.id == ADMIN_CHAT_ID:
    if os.path.exists(SUBSCRIBERS_FILE):
      with open(SUBSCRIBERS_FILE,'r') as count:
       subscribers_data = json.load(count)
       subscribers_count = len(subscribers_data)
       bot.send_message(ADMIN_CHAT_ID,f" Subscribers are now: {subscribers_count}")
   else:
    	bot.send_message(message.chat.id,"unauthorized access to count") 

@bot.message_handler(commands=['p2j'])
def ask_for_py_file(message):
    msg = bot.reply_to(message, "Please send the Python (.py) file you want to convert to a Jupyter notebook (.ipynb).")
    bot.register_next_step_handler(msg, convert_py_to_ipynb)

def convert_py_to_ipynb(message):
    if message.document:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        py_file_path = message.document.file_name

        # Check the file extension if MIME type is not recognized
        if message.document.mime_type == 'text/x-python' or py_file_path.endswith('.py'):
            with open(py_file_path, 'wb') as py_file:
                py_file.write(downloaded_file)

            # Read the Python file
            with open(py_file_path, 'r') as f:
                py_code = f.read()

            # Create a Jupyter notebook
            nb = nbf.new_notebook()
            code_cell = nbf.new_code_cell(py_code)
            nb.cells.append(code_cell)

            # Save as .ipynb file
            ipynb_file_path = py_file_path.replace('.py', '.ipynb')
            with open(ipynb_file_path, 'w') as f:
                nbformat.write(nb, f)

            # Send the converted .ipynb file to the user
            with open(ipynb_file_path, 'rb') as f:
                bot.send_document(message.chat.id, f)

            # Clean up temporary files
            os.remove(py_file_path)
            os.remove(ipynb_file_path)
        else:
            bot.reply_to(message, "The file you sent is not a valid Python (.py) file. Please try again.")
    else:
        bot.reply_to(message, "No file detected. Please try again.")

# Command to handle text-to-speech
@bot.message_handler(commands=['speech'])
def text_to_speech(message):
    bot.reply_to(message, "Please send the text you want to convert to speech. Supported languages: Arabic and English.")

    # Register the next step to handle the text input
    bot.register_next_step_handler(message, handle_text)

def handle_text(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return
    try:
        # Determine the language: Arabic if it contains Arabic characters, otherwise English
        lang = 'ar' if is_arabic_text(message.text) else 'en'

        # Generate speech using gTTS
        tts = gTTS(text=message.text, lang=lang)
        audio_file = f"{message.chat.id}_speech.mp3"
        tts.save(audio_file)

        # Send the audio file to the user
        with open(audio_file, 'rb') as audio:
            bot.send_voice(message.chat.id, audio)

        # Clean up the audio file
        os.remove(audio_file)

    except Exception as e:
        bot.reply_to(message, f"Failed to convert text to speech: {e}")

def is_arabic_text(text):
    # Check if the text contains Arabic characters
    for char in text:
        if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F' or '\u08A0' <= char <= '\u08FF' or '\uFB50' <= char <= '\uFDFF' or '\uFE70' <= char <= '\uFEFF':
            return True
    return False

# Store temporary data for users
user_data = {}

# Command to convert image to PDF
@bot.message_handler(commands=['img_pdf'])
def img_to_pdf(message):
    bot.reply_to(message, "Please send the image you want to convert to PDF.")
    @bot.message_handler(content_types=['photo'])
    def handle_image(message):
        try:
            # Download the image
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            # Save the image temporarily
            img_name = f"{message.chat.id}_image.jpg"
            with open(img_name, 'wb') as new_file:
                new_file.write(downloaded_file)

            # Store the image name in user data
            user_data[message.chat.id] = img_name

            # Ask the user for a name for the PDF
            bot.reply_to(message, "What would you like to name the PDF? (Please send the name without the .pdf extension)")

            # Move on to the next step: waiting for the PDF name
            bot.register_next_step_handler(message, handle_pdf_name)
        except Exception as e:
            bot.reply_to(message, f"Failed to process image: {e}")

def handle_pdf_name(message):
    try:
        pdf_name = f"{message.text}.pdf"
        img_name = user_data.pop(message.chat.id, None)

        if img_name:
            # Convert image to PDF
            image = Image.open(img_name)
            image.save(pdf_name, "PDF", resolution=100.0)

            # Send the PDF to the user
            with open(pdf_name, 'rb') as pdf_file:
                bot.send_document(message.chat.id, pdf_file)

            # Clean up
            os.remove(img_name)
            os.remove(pdf_name)
        else:
            bot.reply_to(message, "No image was found to convert.")

    except Exception as e:
        bot.reply_to(message, f"Failed to rename and convert image to PDF: {e}")

# Command to convert PDF to images
@bot.message_handler(commands=['pdf_img'])
def pdf_to_img(message):
    try:
        # Ask the user to send a PDF after the command
        bot.reply_to(message, "Please send the PDF you want to convert to images.")

        @bot.message_handler(content_types=['document'])
        def handle_pdf(message):
            try:
                # Download the PDF
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)

                # Save the PDF temporarily
                pdf_name = f"{message.chat.id}_document.pdf"
                with open(pdf_name, 'wb') as new_file:
                    new_file.write(downloaded_file)

                # Convert PDF to images
                images = pdf2image.convert_from_path(pdf_name)
                for i, image in enumerate(images):
                    image_name = f"page_{i + 1}.jpg"
                    image.save(image_name, "JPEG")

                    # Send each image to the user
                    with open(image_name, 'rb') as img_file:
                        bot.send_photo(message.chat.id, img_file)

                    # Clean up
                    os.remove(image_name)

                os.remove(pdf_name)
            except Exception as e:
                bot.reply_to(message, f"Failed to convert PDF to images: {e}")

    except Exception as e:
        bot.reply_to(message, f"Failed to start the PDF to image conversion process: {e}")

def notify_admin(message):
    try:
        bot.send_message(ADMIN_CHAT_ID, message)
    except Exception as e:
        print(f"Failed to notify admin: {e}")

def health_check():
    while True:
        time.sleep(
            3600)  # Send a heartbeat every hour (you can adjust the time)
        try:
            bot.send_message(ADMIN_CHAT_ID, "Bot is running")
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")

def notify_shutdown():
    notify_admin("Bot has stopped or is shutting down. Please restart it.")

atexit.register(notify_shutdown)

# Start the health check in a separate thread
health_check_thread = threading.Thread(target=health_check)
health_check_thread.daemon = True  # This ensures the thread will stop when the main program exits
health_check_thread.start()

# Your existing bot code here

HELP = ("This is a study bot which can do this commands :.\n"
        "/start - Start the bot\n"
        "/cancel - Cancel the current operation\n"
        "/help - Show this help message\n"
        "/bisection - solve bisection equations \n"
        "Example: 2**x + 5*x + 2, -1, 0, 0.001\n"
        "/study - display youtube links for subjects.\n"
        "/searchimage - Search for and download an image\n"
        "/python - runs python codes\n"
        "/lecture - allow you to download selected subjects pdfs\n"
       "/img_pdf - allow you to convert images ro pdfs\n"
       "/pdf_img - allow you to convert pdfs to images\n"
       "/p2j - allow you to convert python scripts to juypter scripts\n"
       "/speech - allow you to convert text to speech\n"
       "/report - allow you to report issuses")

# ... (rest of the code remains the same)
@bot.message_handler(commands=['searchimage'])
def search_image_command(message):
    bot.reply_to(message, "Please enter the image search query:")
    bot.register_next_step_handler(message, get_image_count)

def get_image_count(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return
    query = message.text
    bot.reply_to(message,
                 "How many images do you want to download? (Enter a number)")
    bot.register_next_step_handler(message,
                                   lambda msg: search_image(msg, query))

def search_image(message, query):
    try:
        image_count = int(message.text)
        url = f"https://api.unsplash.com/search/photos?query={query}&client_id={UNSPLASH_ACCESS_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['total'] == 0:
                bot.reply_to(message, "No images found for your search query.")
            else:
                photo_urls = [
                    result['urls']['regular'] for result in data['results']
                ]
                for i, url in enumerate(
                        photo_urls[:image_count]
                ):  # Download requested number of images
                    response = requests.get(url)
                    if response.status_code == 200:
                        image = Image.open(BytesIO(response.content))
                        image_file = BytesIO()
                        image.save(image_file, 'JPEG')
                        image_file.seek(0)
                        bot.send_photo(message.chat.id, image_file)
                    else:
                        bot.reply_to(message,
                                     f"Error downloading image {i+1}.")
        else:
            bot.reply_to(message,
                         "Error searching images. Please try again later.")
    except ValueError:
        bot.reply_to(message, "Invalid input. Please enter a number.")

# ... (rest of the code remains the same)

# In-memory tracking
online_users = set()

# Load subscribers from file
if os.path.exists(SUBSCRIBERS_FILE):
    with open(SUBSCRIBERS_FILE, 'r') as f:
        subscribers = set(json.load(f))
else:
    subscribers = set()

if os.path.exists(subjects_url):
    with open(subjects_url,'r') as sub:
        subjects = json.load(sub)

@bot.message_handler(content_types=['new_chat_members'])
def greet_new_member(message):
    for new_member in message.new_chat_members:
        first_name = new_member.first_name or ""
        last_name = new_member.last_name or ""
        username = f"{first_name} {last_name}".strip()
        bot.send_message(
            message.chat.id,
            f"Welcome to the group, {username}! Type /help to get started.")

def bisection_method(func, a, b, tol=0.001):
    steps = []
    if func(a) * func(b) >= 0:
        return "The bisection method cannot be applied due to non existing root", steps

    c = a
    while (b - a) / 2.0 > tol:
        c = (a + b) / 2.0
        steps.append(
            f"a: {a}, b: {b}, c: {c}, f(c): {func(c)}, error: {(b - a) / 2.0}")
        if func(c) == 0:
            return c, steps
        elif func(c) * func(a) < 0:
            b = c
        else:
            a = c

    return c, steps

def save_subscribers():
    with open(SUBSCRIBERS_FILE, 'w') as f:
        json.dump(list(subscribers), f)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    username = f"{first_name} {last_name}".strip()

    bot.reply_to(
        message,
        f"Welcome {username} to MR AWAB study bot!\nUse /help command to see what the bot can do"
    )
    online_users.add(message.chat.id)
    subscribers.add(message.chat.id)
    save_subscribers()

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, HELP)
    online_users.add(message.chat.id)
    save_subscribers()

@bot.message_handler(commands=['cancel'])
def cancel(message):
        bot.clear_step_handler_by_chat_id(message.chat.id)  # Cancel the ongoing operation
        bot.send_message(message.chat.id, "Operation Cancelled")


@bot.message_handler(commands=['clear'])
def clear_history(message):
    bot.reply_to(
        message,
        "Are you sure you want to clear the history? Type 'yes' to confirm.")
    bot.register_next_step_handler(message, confirm_clear)

def confirm_clear(message):
    if message.text.lower() == 'yes':
        # Clear history logic (if needed)
        bot.reply_to(message, "Chat history cleared.")
    else:
        bot.reply_to(message, "Clear history operation cancelled.")

@bot.message_handler(commands=['bisection'])
def bisection_command(message):
    bot.reply_to(message,
                 "Please send your equation, a, b, and tolerance (optional).")
    bot.register_next_step_handler(message, solve_bisection)

@bot.message_handler(commands=['python'])
def python_command(message):
    bot.reply_to(message, "Please send your Python script to run.")
    bot.register_next_step_handler(message, run_python_script)

def solve_bisection(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return
    try:
        data = message.text.split(',')
        func_str = data[0].strip()
        a = float(data[1].strip())
        b = float(data[2].strip())
        tol = float(data[3].strip()) if len(data) > 3 else 0.001

        x = sp.symbols('x')
        func = sp.lambdify(x, sp.sympify(func_str))

        result, steps = bisection_method(func, a, b, tol)

        steps_str = "\n".join(steps)

        bot.reply_to(message, f"Root = {result}\nSteps:\n{steps_str}")
        bot.reply_to(message, "Success")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# Define a set of allowed AST nodes corresponding to SAFE_GLOBALS
ALLOWED_NODES = {
    ast.Module,
    ast.Expr,
    ast.Load,
    ast.Str,
    ast.Num,
    ast.BinOp,
    ast.UnaryOp,
    ast.If,
    ast.Compare,
    ast.FunctionDef,
    ast.Call,
    ast.Assign,
    ast.AugAssign,
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Pass,
    ast.Import,
    ast.ImportFrom,
    ast.alias,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.comprehension,
    ast.ListComp,
    ast.DictComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Break,
    ast.Continue,
    ast.For,
    ast.While,
    ast.IfExp,
    ast.Lambda,
    ast.Try,
    ast.ExceptHandler,
    ast.Raise,
    ast.FormattedValue,
    ast.JoinedStr,
    ast.Constant,
    ast.Store  # Additional nodes for Python 3.6+
}

# Store user-defined variables between script executions
user_variables = {}

def run_python_script(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return
    def execute_script(script, output, safe_globals, safe_locals):
        try:
            with contextlib.redirect_stdout(output):
                exec(script, safe_globals, safe_locals)
        except Exception as e:
            output.write(f"Error: {e}")

    try:
        script = message.text
        tree = ast.parse(script, mode='exec')
        code = compile(tree, filename="<ast>", mode="exec")

        safe_globals = {
            '__builtins__': {
                'print': print,
                'range': range,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'set': set,
                'tuple': tuple,
                'type': type,
                'Exception': Exception,
            }
        }
        safe_locals = user_variables

        output = io.StringIO()
        thread = threading.Thread(target=execute_script,
                                  args=(code, output, safe_globals,
                                        safe_locals))
        thread.start()
        thread.join(timeout=5)  # 5-second timeout

        # Check for unauthorized access
        for node in ast.walk(tree):
            if type(node) not in ALLOWED_NODES:
                bot.reply_to(
                    message,
                    f"Error: Unauthorized access to {node.__class__.__name__}")
                return

        if isinstance(node, ast.Name
                      ) and node.id not in safe_globals and node.id not in dir(
                          __builtins__) and node.id not in user_variables:
            bot.reply_to(message, f"Error: Unauthorized access to {node.id}")
            return

        if thread.is_alive():
            bot.reply_to(message, "Error: Script execution timed out.")
        else:
            result = output.getvalue()
            bot.reply_to(message, f"Output:\n{result}")

    except Exception as e:
        bot.reply_to(message, f"Error: {e}")
        online_users.add(message.chat.id)
        subscribers.add(message.chat.id)
        save_subscribers()

@bot.message_handler(commands=['study'])
def send_study_materials(message):
    markup = InlineKeyboardMarkup()
    for subject, url in subjects.items():
        markup.add(InlineKeyboardButton(subject, url=url))
    bot.send_message(message.chat.id,
                     "Choose a subject to study:",
                     reply_markup=markup)
    online_users.add(message.chat.id)
    subscribers.add(message.chat.id)
    save_subscribers()

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.chat.id == ADMIN_CHAT_ID: 
        bot.reply_to(message, "Please send the message to broadcast.")
        bot.register_next_step_handler(message, send_broadcast)
    else:
        bot.reply_to(message,
                     "You are not authorized to send broadcast messages.")

def send_broadcast(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return
    broadcast_text = message.text
    for chat_id in subscribers:
        try:
            bot.send_message(chat_id, broadcast_text)
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")
    bot.reply_to(message, "Broadcast message sent.")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    username = f"{first_name} {last_name}".strip()

    greetings = ['hi', 'hello', 'hey', 'greetings']
    sdwords = [
        "ÙŠØ§ ÙØ±Ø¯Ø©", "ÙŠØ§ Ø§Ø®ÙˆÙ†Ø§", "ÙŠØ§ Ø´Ø§Ø¨", "ÙŠØ§ Ø¹Ù…Ùƒ", "ÙŠØ§ÙØ±Ø¯Ø©", "ÙŠØ§Ø§Ø®ÙˆÙ†Ø§",
        "ÙŠØ§Ø´Ø§Ø¨", "ÙŠØ§Ø¹Ù…Ùƒ", 'Ø§Ø³Ù…Ø¹Ù†ÙŠ', 'Ø§Ø³Ù…Ø¹', 'Ø´ÙˆÙÙ†Ø§'
    ]

    sdword2 = ['Ø¹ÙˆÙƒ', 'Ø¹ÙˆÙˆÙƒ', 'Ø¹ÙˆÙˆÙˆÙƒ', 'Ø¹ÙˆÙˆÙˆÙˆÙˆÙƒ']
    sdword3 = ['ÙŠØ§Ø²ÙˆÙ„', 'ÙŠØ§Ø²ÙˆÙˆÙˆÙˆÙ„', 'ÙŠØ§Ø²ÙˆÙˆÙ„', 'ÙŠØ§ Ø²ÙˆÙ„', 'ÙŠØ§ Ø²ÙˆÙˆÙ„', 'ÙŠØ§ Ø²ÙˆÙˆÙˆÙ„']
    acknowledgments = [
        'okey', 'thank you', 'thanks', 'okay', 'thanks a lot', 'Ù‚Ø¯Ø§Ù… Ù…Ø§ Ù‚ØµØ±Øª',
        'Ù‚Ø¯Ø§Ù…', 'Ù…Ø§ Ù‚ØµØ±Øª', 'Ø·ÙŠØ¨'
    ]
    Help = ['help', 'Ù…Ø³Ø§Ø¹Ø¯Ù‡', 'Ù‡ÙŠÙ„Ø¨']
    if any(greeting in message.text.lower() for greeting in greetings):
        response = (
            f"Hi {username}! How can I assist you today?\n"
            "Here are the commands you can use:\n"
            "/start - Start the bot\n"
            "/cancel - Cancel the current operation\n"
            "/help - Show help message\n"
            "/bisection function, a, b, tol - Solve equation using Bisection Method\n"
            "/study - Get study materials\n"
            "Example: /bisection 2**x + 5*x + 2, -1, 0, 0.001")
        bot.reply_to(message, response)
    elif any(ack in message.text.lower() for ack in acknowledgments):
        bot.reply_to(message, f"Okey, {username}, Happy to help!")

    elif any(sd in message.text.lower() for sd in sdwords):
        bot.reply_to(
            message,
            "Ø§ÙŠ Ø¬Ù†Ø¨Ùƒ Ø§Ø­ÙƒÙŠ Ù„ÙŠ Ø¹Ø§ÙŠØ² Ø´Ù†Ùˆ \n/start\n/cancel\n/help\n/clear\n/bisection\n/study"
        )
    elif any(sd1 in message.text.lower() for sd1 in sdword2):
        bot.reply_to(
            message,
            "Ø¹ÙˆÙƒ ÙÙŠ Ø±Ø§Ø³Ùƒ Ø¯Ø§ Ø¨ÙˆØª Ù‚Ø±Ø§ÙŠÙ‡ Ø®Ù„ÙŠÙƒ Ø¬Ø§Ø¯ÙŠ \n/start\n/cancel\n/help\n/clear\n/bisection\n/study"
        )
    elif any(sd2 in message.text.lower() for sd2 in sdword3):
        bot.reply_to(
            message,
            "ÙŠØ§ Ø¯ÙØ¹Ø© Ø¬Ø§ÙŠ ØªØ¨Ù‚Ù‰ Ø¯Ø§ÙÙˆØ± ÙˆÙ„Ø§Ù‡ Ø´Ù†Ùˆ Ù‡Ù‡Ù‡Ù‡\n/start\n/cancel\n/help\n/clear\n/bisection\n/study"
        )
    elif any(help in message.text.lower() for help in Help):
        bot.reply_to(message, HELP)
    else:
        # Check if message is a reply
        if message.reply_to_message:
            # Check if reply is from the bot
            if message.reply_to_message.from_user.id == bot.get_me().id:
                bot.reply_to(
                    message,
                    "Sorry, I didn't understand that. Use /help to see available commands."
                )
        else:
            # If it's not a reply, it's a direct message
            bot.reply_to(
                message,
                "Sorry, I didn't understand that. Use /help to see available commands."
            )

    online_users.add(message.chat.id)
    subscribers.add(message.chat.id)


    save_subscribers()

def notify_users_online():
    for chat_id in online_users:
        try:
            bot.send_message(chat_id, "I am back online!")
        except:
            pass

# Notify users when the bot starts up
notify_users_online()
# Start polling with exception handling
while True:
    try:
        bot.polling()
    except Exception as e:
        print(f"Polling error: {e}")
        # Optionally, you can add a delay before retrying
        time.sleep(10)