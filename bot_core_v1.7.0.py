import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
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
flashcards_data = {}
start_time = time.time()
user_state = {}
current_version = "1.7.0"
HELP = ("This is a study bot which can do this commands :\n"
        "/start - Restart the bot\n"
        "/cancel - Cancel the function\n"
        "/subscribe - subscribe to broadcasts\n"
        "/unsubscribe - unsubscribe to broadcasts\n"
        "/lecture - Download selected subject PDFs\n"
        "/img_pdf - Convert images to PDFs\n"
        "/pdf_img - Convert PDFs to images\n"
        "/create_subject - allow you to create specific subject path for flashcards\n"
        "/delete_subject - allow you to delete specific subject path\n"
        "/add_flashcard - Add study flashcards and get quizzed\n"
        "/view_flashcards - Allow you to view saved flashcards\n"
        "/delete_flashcard - Delete a specific flashcard\n"
        "/start_quiz - Quiz you randomly from flashcards\n"
        "/report - Report issues")


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


@bot.message_handler(commands=['start_quiz'])
def start_quiz(message):
    if not flashcards_data:
        bot.send_message(message.chat.id, "No subjects available.")
    else:
        markup = create_subject_buttons(action='quiz')  # Create inline buttons for subjects
        bot.send_message(message.chat.id, "Choose a subject to start the quiz from:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_'))
def quiz_subject(call):
    subject = call.data.split('_')[1]
    user_id = str(call.message.chat.id)

    user_flashcards = flashcards_data.get(subject, {}).get(user_id, [])

    if not user_flashcards:
        bot.send_message(call.message.chat.id, f"No flashcards found in {subject} to quiz on.")
    else:
        bot.send_message(call.message.chat.id, f"Starting quiz for {subject}!")
        ask_question(call.message, subject)

def ask_question(message, subject):
    user_flashcards = flashcards_data.get(subject, {}).get(str(message.chat.id), [])
    if not user_flashcards:
        bot.send_message(message.chat.id, "No flashcards available.")
        return

    question_card = random.choice(user_flashcards)
    user_state[message.chat.id] = {"question": question_card, "subject": subject}

    bot.send_message(message.chat.id, f"Question: {question_card['question']}")
    bot.register_next_step_handler(message, check_answer)

def check_answer(message):
    correct_answer = user_state[message.chat.id]["question"]["answer"]
    user_answer = message.text
    subject = user_state[message.chat.id]["subject"]

    if user_answer.lower() == correct_answer.lower():
        bot.send_message(message.chat.id, f"Correct! Want to try another one from {subject}? /start_quiz")
    else:
        bot.send_message(message.chat.id, f"Wrong! The correct answer was: {correct_answer}. Try again with /start_quiz")

def create_subject_buttons(action='add'):
    markup = InlineKeyboardMarkup()
    for subject in flashcards_data.keys():
        callback_data = f"{action}_{subject}"
        markup.add(InlineKeyboardButton(subject, callback_data=callback_data))
    return markup


@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    chat_id = message.chat.id
    if chat_id in subscribers:
        bot.reply_to(message, "You are already subscribed.")
    else:
        subscribers.add(chat_id)
        save_subscribers()
        bot.reply_to(message, "You have been subscribed successfully.")


@bot.message_handler(commands=['unsubscribe'])
def unsubscribe(message):
    chat_id = message.chat.id
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers()
        bot.reply_to(message, "You have been unsubscribed successfully.")
    else:
        bot.reply_to(message, "You are not subscribed.")


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


@bot.message_handler(commands=['report'])
def report_issue(message):
    bot.reply_to(message, "Please describe the issue you're facing:")
    bot.register_next_step_handler(message, handle_report)

def handle_report(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return
    # Construct the clickable link using Telegram markdown
    report_text = f"Report from user <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name} {message.from_user.last_name}</a> : \n\n{message.text}"
    bot.send_message(AWAB_CHAT_ID, report_text, parse_mode='HTML')
    bot.reply_to(message, "Thank you for your report! We'll look into it.")


@bot.message_handler(commands=['cancel'])
def cancel(message):
        bot.clear_step_handler_by_chat_id(message.chat.id)  # Cancel the ongoing operation
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
    if message.content_type == "photo":# Ensure it's a document
        photo_id = message.photo[-1].file_id
        bot.send_message(2134611910, f"Payment made from {user_name}")
        user_id = message.chat.id
        bot.send_message(2134611910, "with chat ID")
        bot.send_message(2134611910, user_id)
        bot.send_photo(2134611910, photo_id)
        bot.reply_to(message, "Payment confirmed. Thank you!")
    else:
        bot.reply_to(message, "Please send a valid receipt (document).")
        bot.register_next_step_handler(message, handle_payment, user_name)

@bot.message_handler(commands=["my_id"])
def my_id(message):
    user_id = message.chat.id
    bot.send_message(message.chat.id, user_id)


##################################

##########ADMIN COMMANDS#########

@bot.message_handler(commands=["send_message"])
def send_message(message):
    if message.chat.id in ADMIN_CHAT_ID:
        msg = bot.reply_to(message, "Enter your message")
        bot.register_next_step_handler(msg, get_message_content)
    else:
        bot.reply_to(message, "Unauthorized access")

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


@bot.message_handler(commands=['nofs'])
def send_subscribers_names(message):
    if message.chat.id == AWAB_CHAT_ID:
        names_list = []
        subscribers_names = list(subscribers)
        for chat_id in subscribers_names:
            try:
               user_info = bot.get_chat(chat_id)
            # You can choose either full_name or username
               first_name = user_info.first_name or "unknown"
               second_name = user_info.last_name or ""
               user_name = user_info.username or "no username"
               full_name = f"{first_name} {second_name} ({user_name})"
               names_list.append(full_name)
            except telebot.apihelper.ApiTelegramException:
               names_list.append(f"ID: {chat_id} (Name not found)")

        names_text = "\n".join(names_list)
        bot.send_message(AWAB_CHAT_ID, f"Subscribers:\n\n{names_text}")

    elif message.chat.id == AMAR_CHAT_ID:
        names_list = []
        subscribers_names = list(subscribers)
        for chat_id in subscribers_names:
            try:
               user_info = bot.get_chat(chat_id)
            # You can choose either full_name or username
               first_name = user_info.first_name or "unknown"
               second_name = user_info.last_name or ""
               user_name = user_info.username or "no username"
               full_name = f"{first_name} {second_name} ({user_name})"
               names_list.append(full_name)
            except telebot.apihelper.ApiTelegramException:
               names_list.append(f"ID: {chat_id} (Name not found)")

        names_text = "\n".join(names_list)
        bot.send_message(AMAR_CHAT_ID, f"Subscribers:\n\n{names_text}")
    else:
        bot.reply_to(message,"You are not authorized to access nofs")

# Global variable to track the last file upload time
last_upload_time = None


@bot.message_handler(commands=['upload'])
def request_upload_code(message):
    if message.chat.id in ADMIN_CHAT_ID:
        bot.reply_to(message, "Please enter the code for your department to upload files:")
        bot.register_next_step_handler(message, process_upload_code)
    else:
        bot.reply_to(message, "You are not authorized to access upload.")

def process_upload_code(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return

    code = message.text.strip()

    department_codes = {
        "3030": "electronics",
        "4040": "mechatronics",
        "5050": "biomedical",
        "6060": "computer",
        "7070": "t.com"
    }

    department = department_codes.get(code)
    if not department:
        bot.reply_to(message, "Invalid code. Please enter a valid code.")
        return

    bot.reply_to(message, f"Department: {department}. Please enter the subject name:")
    bot.register_next_step_handler(message, process_subject_name, department)

def process_subject_name(message, department):
    if message.text.lower() == "/cancel":
        cancel(message)
        return

    subject_name = message.text.strip()

    bot.reply_to(message, f"Subject: {subject_name}. Please upload all PDF or PPTX files (you can upload multiple files in one go):")
    bot.register_next_step_handler(message, process_multiple_file_uploads, department, subject_name)

def process_multiple_file_uploads(message, department, subject_name):
    global last_upload_time

    if not message.document :
        bot.reply_to(message, "Invalid document format.")
        return

    if department not in subject_pdfs:
        subject_pdfs[department] = {}
    if subject_name not in subject_pdfs[department]:
        subject_pdfs[department][subject_name] = []

    subject_dir = os.path.join(subject_file, department, subject_name)
    os.makedirs(subject_dir, exist_ok=True)

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    file_path = os.path.join(subject_dir, message.document.file_name)
    with open(file_path, 'wb') as file:
        file.write(downloaded_file)

    subject_pdfs[department][subject_name].append(file_path)

    # Update last upload time
    last_upload_time = time.time()

    # Save the updated JSON file
    with open(subjects_json, 'w') as f:
        json.dump(subject_pdfs, f, indent=4)

    bot.reply_to(message, f"File uploaded successfully to {subject_name} under {department}.")

    # Set a timer to check if 60 seconds have passed since the last upload
    bot.reply_to(message, "Waiting for more files... If no new file is uploaded within 60 seconds, the session will close.")
    bot.register_next_step_handler(message, wait_for_timeout, department, subject_name)

def wait_for_timeout(message, department, subject_name):
    global last_upload_time

    # Check if 60 seconds have passed since the last upload
    if time.time() - last_upload_time > 60:
        bot.reply_to(message, "No files uploaded in the last 60 seconds. Session closed.")
        return  # End the session
    else:
        # Wait for the next file upload or another command
        process_multiple_file_uploads(message, department, subject_name)


@bot.message_handler(commands=['count'])
def count(message):
    if message.chat.id in ADMIN_CHAT_ID:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE,'r') as count:
                subscribers_data = json.load(count)
                subscribers_count = len(subscribers_data)
                bot.send_message(AWAB_CHAT_ID,f" Subscribers are now: {subscribers_count}")
    else:
        bot.reply_to(message,"unauthorized access to count")

# Store temporary data for users
user_data = {}

# Command to convert image to PD
# Store user-defined variables between script executions
user_variables = {}

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.chat.id in ADMIN_CHAT_ID:
        bot.reply_to(message, "Please send the message or file to broadcast.")
        bot.register_next_step_handler(message, send_broadcast)
    else:
        bot.reply_to(message, "You are not authorized to send broadcast messages.")

def send_broadcast(message):
    if message.text.lower() == "/cancel":
        cancel(message)
        return

    if message.text:  # If it's a text message
        broadcast_content = message.text
        for chat_id in subscribers:
            try:
                bot.send_message(chat_id, broadcast_content)
            except Exception as e:
                print(f"Failed to send message to {chat_id}: {e}")
    elif message.document:  # If it's a document (PDF, PPTX, etc.)
        file_id = message.document.file_id
        file_name = message.document.file_name
        for chat_id in subscribers:
            try:
                bot.send_document(chat_id, file_id, caption=f"Broadcasting {file_name}")
            except Exception as e:
                print(f"Failed to send document to {chat_id}: {e}")
    elif message.audio:  # If it's an audio file
        file_id = message.audio.file_id
        for chat_id in subscribers:
            try:
                bot.send_audio(chat_id, file_id, caption="Broadcasting an audio file.")
            except Exception as e:
                print(f"Failed to send audio to {chat_id}: {e}")
    elif message.video:  # If it's a video
        file_id = message.video.file_id
        for chat_id in subscribers:
            try:
                bot.send_video(chat_id, file_id, caption="Broadcasting a video.")
            except Exception as e:
                print(f"Failed to send video to {chat_id}: {e}")

    bot.reply_to(message, "Broadcast message sent.")


@bot.message_handler(commands=['up_time'])
def up_time(message):
    if message.chat.id in ADMIN_CHAT_ID:
        current_time = time.time()
        elapsed_time = current_time - start_time
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        up_time_str = f"Bot has been running for {int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds."
        bot.reply_to(message, up_time_str)
    else:
        bot.reply_to(message," You are not authorized to see up time")


###################################

######FUNCTIONS FOR COMMANDS#########################

def save_subscribers():
     with open(SUBSCRIBERS_FILE, 'w') as f:
        json.dump(list(subscribers), f)

def save_flashcards(flashcards):
    with open(FLASHCARDS_FILE, 'w') as f:
        json.dump(flashcards, f)

def load_responses():
    with open('response.json', 'r') as file:
        return json.load(file)

if os.path.exists(SUBSCRIBERS_FILE):
    with open(SUBSCRIBERS_FILE, 'r') as f:
        subscribers = set(json.load(f))

responses = load_responses()
if os.path.exists(subjects_json):
    with open(subjects_json, 'r') as f:
        subject_pdfs = json.load(f)
else:
    subject_pdfs = {}

if os.path.exists(subjects_url):
    with open(subjects_url,'r') as sub:
        subjects = json.load(sub)

###################################

########CHAT BOT###################

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    username = f"{first_name} {last_name}".strip()

    commands = [
        "start", "cancel", "lecture", "img_pdf",
        "pdf_img", "create_subject", "delete_subject",
        "add_flashcard", "view_flashcards", "delete_flashcard", "import_flashcards", "export_flashcards", "start_quiz",
        "help", "subscribe", "unsubscribe", "about_me", "report", "up_time", "nofs", "count", "broadcast", "upload","send_message","donate", "my_id"
    ]

    greetings = responses["greetings"]
    acknowledgments = responses["acknowledgments"]
    help_keywords = responses["help_keywords"]
    compliments = responses["compliments"]
    farewells = responses["farewells"]
    jokes = responses["jokes"]
    jokes_trigger = responses["jokes_trigger"]

    text_lower = message.text.lower()

    # Debugging: print received message
    print("Message received:", text_lower)

    if any(greeting in text_lower for greeting in greetings):
        response = f"Hi {username}! How can I assist you today?"
        bot.reply_to(message, response)

    elif any(trigger in text_lower for trigger in jokes_trigger):
        response = random.choice(jokes)  # Randomly select a joke
        bot.reply_to(message, response)

    elif any(ack in text_lower for ack in acknowledgments):
        response = f"You're welcome, {username}! If you need anything else, just ask!"
        bot.reply_to(message, response)

    elif any(help in text_lower for help in help_keywords):
        response = (
            "I'm here to help you! Here are some things you can do:\n"
            "/help - Get assistance\n"
            "/subscribe - Subscribe for updates\n"
            "/unsubscribe - Unsubscribe from updates\n"
            "Feel free to ask me anything else, and I'll do my best to assist you!"
        )
        bot.reply_to(message, response)

    elif any(comp in text_lower for comp in compliments):
        response = f"Aww, thanks, {username}! You're amazing too! If you need anything, just let me know!"
        bot.reply_to(message, response)

    elif any(farewell in text_lower for farewell in farewells):
        response = f"Goodbye {username}! Take care and feel free to reach out anytime. ðŸ‘‹"
        bot.reply_to(message, response)

    elif text_lower.startswith("/"):
        command = text_lower.split()[0][1:]
        if command not in commands:
            bot.reply_to(message, "Command is unknown...")

    elif message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id:
        response = "Hmm, I didn't quite get that ðŸ˜…. Maybe try using /help to see what I can do!"
        bot.reply_to(message, response)

    else:
        bot.reply_to(
            message,
            "Sorry, I didn't understand that ðŸ˜•. Use /help to see available commands or ask for assistance!"
        )

###################################

if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True, timeout=120, long_polling_timeout=120)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(10)

##################################