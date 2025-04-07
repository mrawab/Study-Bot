import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from telebot import types
import json
import os
import time
import pdf2image
from PIL import Image
import zipfile
import random
import csv
from dotenv import load_dotenv
load_dotenv()

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_API"))
ADMIN_CHAT_ID = (ADMINimport telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from telebot import types
import json
import os
import time
import pdf2image
from PIL import Image
import zipfile
import random
import csv
from dotenv import load_dotenv
load_dotenv()

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_API"))
ADMIN_CHAT_ID = (ADMIN_CHAT_ID , ADMIN_CHAT_ID, ADMIN_CHAT_ID, ADMIN_CHAT_ID)
AMAR_CHAT_ID = None
AWAB_CHAT_ID = None
subjects_url = "subjects_url.json"
SUBSCRIBERS_FILE = "subscribers.json"
subjects_json = "subjects_json.json"
subject_file = "/home/mrawab/subjects_pdfs"
FLASHCARDS_FILE = 'flashcards.json'
SUBJECT_FILE = "subject_channels.json"
flashcards_data = {}
start_time = time.time()
user_state = {}
current_version = "1.8.0"
HELP = ("This is a study bot which can do this commands :\n"
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
        "/start_quiz - Quiz you randomly from flashcards\n"
        "/report - Report issues")
        
department_map = {
    "3030": "electronics",
    "4040": "mechatronics",
    "5050": "biomedical",
    "6060": "computer",
    "7070": "t.com"
}

##########USERS COMMANDS#########

@bot.message_handler(commands=['start'])
def send_welcome(message):
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    username = f"{first_name} {last_name}".strip()

    bot.reply_to(
        message,
        f"Welcome {username} to MR AWAB study bot!\nUse /help command to see what the bot can do"
    )


@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, HELP)


@bot.message_handler(commands=["about_me"])
def about_me(message):
    bot.reply_to(
        message,
        f"Study Bot patch {current_version}:\n"
        "I'm a study designed to help you study and access pdfs easily\n"
        "bot created by Awab Azhari\n"
        "Want to find out more about me? Check my website:\n"
        "[Awab Azhari](https://awabazhari.netlify.app)\n"
        "Or find my Facebook page:\n"
        "[Facebook Page](https://www.facebook.com/awabazharii?mibextid=ZbWKwL)",
        parse_mode="Markdown"
    )


@bot.message_handler(content_types=['new_chat_members'])
def greet_new_member(message):
    for new_member in message.new_chat_members:
        first_name = new_member.first_name or ""
        last_name = new_member.last_name or ""
        username = f"{first_name} {last_name}".strip()
        bot.send_message(
            message.chat.id,
            f"Welcome to the group, {username}! Type /help to get started.")


@bot.message_handler(commands=['create_subject'])
def create_subject(message):
    bot.send_message(message.chat.id, "Please enter the name of the new subject:")
    bot.register_next_step_handler(message, save_new_subject)

def save_new_subject(message):
    subject_name = message.text.strip()

    # Check if the subject already exists
    if subject_name in flashcards_data:
        bot.send_message(message.chat.id, f"The subject '{subject_name}' already exists. Please use a different name or /add_flashcard to add flashcards.")
    else:
        # Create the new subject
        flashcards_data[subject_name] = {}
        save_flashcards(flashcards_data)  # Save the updated data
        bot.send_message(message.chat.id, f"Subject '{subject_name}' created successfully! You can now add flashcards using /add_flashcard.")


# Command to delete a subject
@bot.message_handler(commands=['delete_subject'])
def delete_subject(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects are available to delete.")
        return

    markup = InlineKeyboardMarkup()
    for subject in flashcards_data.keys():
        callback_data = f"delete_{subject.replace(' ', '_')}"
        markup.add(InlineKeyboardButton(subject, callback_data=callback_data))

    bot.send_message(message.chat.id, "Select a subject to delete:", reply_markup=markup)

# Callback handler for subject deletion
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def confirm_delete_subject(call):
    subject_name = call.data.split('_', 1)[1].replace('_', ' ')

    # Ask for confirmation before deleting the subject
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Yes", callback_data=f"confirm_delete_{subject_name.replace(' ', '_')}"))
    markup.add(InlineKeyboardButton("No", callback_data="cancel_delete"))

    bot.send_message(call.message.chat.id, f"Are you sure you want to delete the subject '{subject_name}'?", reply_markup=markup)

# Handle the confirmation or cancellation of the deletion
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_') or call.data == 'cancel_delete')
def handle_delete_confirmation(call):
    if call.data == 'cancel_delete':
        bot.send_message(call.message.chat.id, "Subject deletion canceled.")
        return

    subject_name = call.data.split('_', 2)[2].replace('_', ' ')

    # Delete the subject and update the JSON file
    if subject_name in flashcards_data:
        del flashcards_data[subject_name]
        save_flashcards(flashcards_data)  # Save the updated data
        bot.send_message(call.message.chat.id, f"Subject '{subject_name}' has been deleted.")
    else:
        bot.send_message(call.message.chat.id, f"Subject '{subject_name}' not found.")


@bot.message_handler(commands=['add_flashcard'])
def request_subject(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available. Please add a new subject first.")
    else:
        markup = create_subject_buttons()  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to add flashcards to:", reply_markup=markup)

# Callback handler for adding flashcards
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_'))
def get_subject_for_flashcard(call):
    subject = call.data.split('_')[1]
    user_id = str(call.message.chat.id)

    if subject not in flashcards_data:
        flashcards_data[subject] = {}

    if user_id not in flashcards_data[subject]:
        flashcards_data[subject][user_id] = []

    bot.send_message(call.message.chat.id, f"Adding flashcard to {subject}. Send the question:")
    bot.register_next_step_handler(call.message, lambda msg: get_question(msg, subject))

def get_question(message, subject):
    question = message.text
    bot.send_message(message.chat.id, "Now send the answer:")
    bot.register_next_step_handler(message, lambda msg: save_flashcard(msg, question, subject))

def save_flashcard(message, question, subject):
    answer = message.text
    user_id = str(message.chat.id)

    flashcards_data[subject][user_id].append({"question": question, "answer": answer})
    save_flashcards(flashcards_data)
    bot.send_message(message.chat.id, f"Flashcard added to {subject}! Use /view_flashcards to see them or /add_flashcard to add more.")


@bot.message_handler(commands=['view_flashcards'])
def view_flashcards(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action='view')  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to view flashcards from:", reply_markup=markup)

# Callback handler to display flashcards
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def show_flashcards(call):
    subject = call.data.split('_')[1]
    user_id = str(call.message.chat.id)

    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])

    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject}.")
    else:
        for index, card in enumerate(user_flashcards):
            bot.send_message(call.message.chat.id, f"Flashcard {index + 1}:\nQ: {card['question']}\nA: {card['answer']}")


@bot.message_handler(commands=['delete_flashcard'])
def delete_flashcard(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action='delete')  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to delete flashcards from:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def select_flashcard_to_delete(call):
    subject = call.data.split('_')[1]
    user_id = str(call.message.chat.id)

    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])

    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject}.")
    else:
        markup = InlineKeyboardMarkup()
        for index, card in enumerate(user_flashcards):
            markup.add(InlineKeyboardButton(
                text=f"Flashcard {index + 1}: {card['question']}",
                callback_data=f"delete_card_{subject}_{index}"
            ))
        bot.send_message(call.message.chat.id, "Select a flashcard to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_card_'))
def delete_selected_flashcard(call):
    _, subject, index = call.data.split('_')
    user_id = str(call.message.chat.id)
    index = int(index)

    user_flashcards = flashcards_data[subject][user_id]
    deleted_flashcard = user_flashcards.pop(index)
    save_flashcards(flashcards_data)

    bot.send_message(call.message.chat.id, f"Deleted flashcard:\nQ: {deleted_flashcard['question']}\nA: {deleted_flashcard['answer']}")


@bot.message_handler(commands=['import_flashcards', 'export_flashcards'])
def handle_csv(message):
    command = message.text.strip('/')
    if command == 'export_flashcards':
        export_flashcards(message.chat.id)
    elif command == 'import_flashcards':
        bot.send_message(message.chat.id, "Send the CSV file to import flashcards:")
        bot.register_next_step_handler(message, import_flashcards)

def export_flashcards(chat_id):
    file_path = "/tmp/flashcards.csv"
    with open(file_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Subject', 'Question', 'Answer'])
        for subject, users in flashcards_data.items():
            for user_id, flashcards in users.items():
                for card in flashcards:
                    writer.writerow([subject, card['question'], card['answer']])

    with open(file_path, 'rb') as f:
        bot.send_document(chat_id, f)

def import_flashcards(message):
    if not message.document:
        bot.send_message(message.chat.id, "No file sent. Please send a valid CSV file.")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    try:
        content = downloaded_file.decode('utf-8').splitlines()
        reader = csv.DictReader(content)
        for row in reader:
            subject = row['Subject']
            question = row['Question']
            answer = row['Answer']
            user_id = str(message.chat.id)

            if subject not in flashcards_data:
                flashcards_data[subject] = {}

            if user_id not in flashcards_data[subject]:
                flashcards_data[subject][user_id] = []

            flashcards_data[subject][user_id].append({"question": question, "answer": answer})

        save_flashcards(flashcards_data)
        bot.send_message(message.chat.id, "Flashcards imported successfully!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Failed to import flashcards: {e}")


@bot.message_handler(commands=['lecture'])
def request_code(message):
    bot.reply_to(message, "Please enter the code for your department:")
    bot.send_message(message.chat.id, "3030 for Electronics batch\n"
    "4040 for Mechatronics batch\n"
    "5050 for Biomedical batch\n"
    "6060 for Computer batch\n"
    "7070 for Telecom batch")
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
    elif code == "5050":
        bot.send_message(message.chat.id, "Biomedical batch")
        send_pdf_list(message, "biomedical")
    elif code == "6060":
        bot.send_message(message.chat.id, "Computer batch")
        send_pdf_list(message, "computer")
    elif code == "7070":
        bot.send_message(message.chat.id, "T.com batch")
        send_pdf_list(message, "t.com")
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

@bot.message_handler(commands=['lecture_video'])
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
    
@bot.message_handler(commands=['start_quiz'])
def start_quiz(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action='quiz')  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to start the quiz from:", reply_markup=markup)

@b_CHAT_ID , ADMIN_CHAT_ID, ADMIN_CHAT_ID, ADMIN_CHAT_ID)
AMAR_CHAT_ID = None
AWAB_CHAT_ID = None
subjects_url = "subjects_url.json"
SUBSCRIBERS_FILE = "subscribers.json"
subjects_json = "subjects_json.json"
subject_file = "/home/mrawab/subjects_pdfs"
FLASHCARDS_FILE = 'flashcards.json'
SUBJECT_FILE = "subject_channels.json"
flashcards_data = {}
start_time = time.time()
user_state = {}
current_version = "1.8.0"
HELP = ("This is a study bot which can do this commands :\n"
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
        "/start_quiz - Quiz you randomly from flashcards\n"
        "/report - Report issues")
        
department_map = {
    "3030": "electronics",
    "4040": "mechatronics",
    "5050": "biomedical",
    "6060": "computer",
    "7070": "t.com"
}

##########USERS COMMANDS#########

@bot.message_handler(commands=['start'])
def send_welcome(message):
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    username = f"{first_name} {last_name}".strip()

    bot.reply_to(
        message,
        f"Welcome {username} to MR AWAB study bot!\nUse /help command to see what the bot can do"
    )


@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, HELP)


@bot.message_handler(commands=["about_me"])
def about_me(message):
    bot.reply_to(
        message,
        f"Study Bot patch {current_version}:\n"
        "I'm a study designed to help you study and access pdfs easily\n"
        "bot created by Awab Azhari\n"
        "Want to find out more about me? Check my website:\n"
        "[Awab Azhari](https://awabazhari.netlify.app)\n"
        "Or find my Facebook page:\n"
        "[Facebook Page](https://www.facebook.com/awabazharii?mibextid=ZbWKwL)",
        parse_mode="Markdown"
    )


@bot.message_handler(content_types=['new_chat_members'])
def greet_new_member(message):
    for new_member in message.new_chat_members:
        first_name = new_member.first_name or ""
        last_name = new_member.last_name or ""
        username = f"{first_name} {last_name}".strip()
        bot.send_message(
            message.chat.id,
            f"Welcome to the group, {username}! Type /help to get started.")


@bot.message_handler(commands=['create_subject'])
def create_subject(message):
    bot.send_message(message.chat.id, "Please enter the name of the new subject:")
    bot.register_next_step_handler(message, save_new_subject)

def save_new_subject(message):
    subject_name = message.text.strip()

    # Check if the subject already exists
    if subject_name in flashcards_data:
        bot.send_message(message.chat.id, f"The subject '{subject_name}' already exists. Please use a different name or /add_flashcard to add flashcards.")
    else:
        # Create the new subject
        flashcards_data[subject_name] = {}
        save_flashcards(flashcards_data)  # Save the updated data
        bot.send_message(message.chat.id, f"Subject '{subject_name}' created successfully! You can now add flashcards using /add_flashcard.")


# Command to delete a subject
@bot.message_handler(commands=['delete_subject'])
def delete_subject(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects are available to delete.")
        return

    markup = InlineKeyboardMarkup()
    for subject in flashcards_data.keys():
        callback_data = f"delete_{subject.replace(' ', '_')}"
        markup.add(InlineKeyboardButton(subject, callback_data=callback_data))

    bot.send_message(message.chat.id, "Select a subject to delete:", reply_markup=markup)

# Callback handler for subject deletion
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def confirm_delete_subject(call):
    subject_name = call.data.split('_', 1)[1].replace('_', ' ')

    # Ask for confirmation before deleting the subject
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Yes", callback_data=f"confirm_delete_{subject_name.replace(' ', '_')}"))
    markup.add(InlineKeyboardButton("No", callback_data="cancel_delete"))

    bot.send_message(call.message.chat.id, f"Are you sure you want to delete the subject '{subject_name}'?", reply_markup=markup)

# Handle the confirmation or cancellation of the deletion
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_') or call.data == 'cancel_delete')
def handle_delete_confirmation(call):
    if call.data == 'cancel_delete':
        bot.send_message(call.message.chat.id, "Subject deletion canceled.")
        return

    subject_name = call.data.split('_', 2)[2].replace('_', ' ')

    # Delete the subject and update the JSON file
    if subject_name in flashcards_data:
        del flashcards_data[subject_name]
        save_flashcards(flashcards_data)  # Save the updated data
        bot.send_message(call.message.chat.id, f"Subject '{subject_name}' has been deleted.")
    else:
        bot.send_message(call.message.chat.id, f"Subject '{subject_name}' not found.")


@bot.message_handler(commands=['add_flashcard'])
def request_subject(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available. Please add a new subject first.")
    else:
        markup = create_subject_buttons()  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to add flashcards to:", reply_markup=markup)

# Callback handler for adding flashcards
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_'))
def get_subject_for_flashcard(call):
    subject = call.data.split('_')[1]
    user_id = str(call.message.chat.id)

    if subject not in flashcards_data:
        flashcards_data[subject] = {}

    if user_id not in flashcards_data[subject]:
        flashcards_data[subject][user_id] = []

    bot.send_message(call.message.chat.id, f"Adding flashcard to {subject}. Send the question:")
    bot.register_next_step_handler(call.message, lambda msg: get_question(msg, subject))

def get_question(message, subject):
    question = message.text
    bot.send_message(message.chat.id, "Now send the answer:")
    bot.register_next_step_handler(message, lambda msg: save_flashcard(msg, question, subject))

def save_flashcard(message, question, subject):
    answer = message.text
    user_id = str(message.chat.id)

    flashcards_data[subject][user_id].append({"question": question, "answer": answer})
    save_flashcards(flashcards_data)
    bot.send_message(message.chat.id, f"Flashcard added to {subject}! Use /view_flashcards to see them or /add_flashcard to add more.")


@bot.message_handler(commands=['view_flashcards'])
def view_flashcards(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action='view')  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to view flashcards from:", reply_markup=markup)

# Callback handler to display flashcards
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def show_flashcards(call):
    subject = call.data.split('_')[1]
    user_id = str(call.message.chat.id)

    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])

    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject}.")
    else:
        for index, card in enumerate(user_flashcards):
            bot.send_message(call.message.chat.id, f"Flashcard {index + 1}:\nQ: {card['question']}\nA: {card['answer']}")


@bot.message_handler(commands=['delete_flashcard'])
def delete_flashcard(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action='delete')  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to delete flashcards from:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def select_flashcard_to_delete(call):
    subject = call.data.split('_')[1]
    user_id = str(call.message.chat.id)

    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])

    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject}.")
    else:
        markup = InlineKeyboardMarkup()
        for index, card in enumerate(user_flashcards):
            markup.add(InlineKeyboardButton(
                text=f"Flashcard {index + 1}: {card['question']}",
                callback_data=f"delete_card_{subject}_{index}"
            ))
        bot.send_message(call.message.chat.id, "Select a flashcard to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_card_'))
def delete_selected_flashcard(call):
    _, subject, index = call.data.split('_')
    user_id = str(call.message.chat.id)
    index = int(index)

    user_flashcards = flashcards_data[subject][user_id]
    deleted_flashcard = user_flashcards.pop(index)
    save_flashcards(flashcards_data)

    bot.send_message(call.message.chat.id, f"Deleted flashcard:\nQ: {deleted_flashcard['question']}\nA: {deleted_flashcard['answer']}")


@bot.message_handler(commands=['import_flashcards', 'export_flashcards'])
def handle_csv(message):
    command = message.text.strip('/')
    if command == 'export_flashcards':
        export_flashcards(message.chat.id)
    elif command == 'import_flashcards':
        bot.send_message(message.chat.id, "Send the CSV file to import flashcards:")
        bot.register_next_step_handler(message, import_flashcards)

def export_flashcards(chat_id):
    file_path = "/tmp/flashcards.csv"
    with open(file_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Subject', 'Question', 'Answer'])
        for subject, users in flashcards_data.items():
            for user_id, flashcards in users.items():
                for card in flashcards:
                    writer.writerow([subject, card['question'], card['answer']])

    with open(file_path, 'rb') as f:
        bot.send_document(chat_id, f)

def import_flashcards(message):
    if not message.document:
        bot.send_message(message.chat.id, "No file sent. Please send a valid CSV file.")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    try:
        content = downloaded_file.decode('utf-8').splitlines()
        reader = csv.DictReader(content)
        for row in reader:
            subject = row['Subject']
            question = row['Question']
            answer = row['Answer']
            user_id = str(message.chat.id)

            if subject not in flashcards_data:
                flashcards_data[subject] = {}

            if user_id not in flashcards_data[subject]:
                flashcards_data[subject][user_id] = []

            flashcards_data[subject][user_id].append({"question": question, "answer": answer})

        save_flashcards(flashcards_data)
        bot.send_message(message.chat.id, "Flashcards imported successfully!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Failed to import flashcards: {e}")


@bot.message_handler(commands=['lecture'])
def request_code(message):
    bot.reply_to(message, "Please enter the code for your department:")
    bot.send_message(message.chat.id, "3030 for Electronics batch\n"
    "4040 for Mechatronics batch\n"
    "5050 for Biomedical batch\n"
    "6060 for Computer batch\n"
    "7070 for Telecom batch")
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
    elif code == "5050":
        bot.send_message(message.chat.id, "Biomedical batch")
        send_pdf_list(message, "biomedical")
    elif code == "6060":
        bot.send_message(message.chat.id, "Computer batch")
        send_pdf_list(message, "computer")
    elif code == "7070":
        bot.send_message(message.chat.id, "T.com batch")
        send_pdf_list(message, "t.com")
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

@bot.message_handler(commands=['lecture_video'])
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
    
@bot.message_handler(commands=['start_quiz'])
def start_quiz(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action='quiz')  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to start the quiz from:", reply_markup=markup)

@b
