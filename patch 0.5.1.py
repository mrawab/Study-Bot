import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import sympy as sp
import json
import os
import requests
import io
import contextlib
import ast
import threading
from io import BytesIO
from PIL import Image

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot = telebot.TeleBot('6682482527:AAH1jipGApDYSX_4pt6o5l1dai7jTwI2Xz0')
# Add your Unsplash API key
UNSPLASH_ACCESS_KEY = 'yQGFRNNIiTUJnYc3CUX1wOhDBm73gJ9ktNpdSG0wEiM'

HELP = (
    "This is a study bot which can do this commands :.\n"
    "/start - Start the bot\n"
    "/cancel - Cancel the current operation\n"
    "/help - Show this help message\n"
    "/bisection - solve bisection equations \n"
    "Example: 2**x + 5*x + 2, -1, 0, 0.001\n"
    "/study - display youtube links for subjects.\n"
    "/searchimage - Search for and download an image\n"
    "/python - runs python code"
)

# ... (rest of the code remains the same)
@bot.message_handler(commands=['searchimage'])
def search_image_command(message):
    bot.reply_to(message, "Please enter the image search query:")
    bot.register_next_step_handler(message, get_image_count)

def get_image_count(message):
    query = message.text
    bot.reply_to(message, "How many images do you want to download? (Enter a number)")
    bot.register_next_step_handler(message, lambda msg: search_image(msg, query))

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
                photo_urls = [result['urls']['regular'] for result in data['results']]
                for i, url in enumerate(photo_urls[:image_count]):  # Download requested number of images
                    response = requests.get(url)
                    if response.status_code == 200:
                        image = Image.open(BytesIO(response.content))
                        image_file = BytesIO()
                        image.save(image_file, 'JPEG')
                        image_file.seek(0)
                        bot.send_photo(message.chat.id, image_file)
                    else:
                        bot.reply_to(message, f"Error downloading image {i+1}.")
        else:
            bot.reply_to(message, "Error searching images. Please try again later.")
    except ValueError:
        bot.reply_to(message, "Invalid input. Please enter a number.")

# ... (rest of the code remains the same)

# In-memory tracking
online_users = set()

# File to store subscribers
SUBSCRIBERS_FILE = 'subscribers.json'

# Load subscribers from file
if os.path.exists(SUBSCRIBERS_FILE):
    with open(SUBSCRIBERS_FILE, 'r') as f:
        subscribers = set(json.load(f))
else:
    subscribers = set()

subjects = {
    "Special functions": "https://youtube.com/playlist?list=PLOncQI9Od7F_BhnmXnPqG0vPRBkTmH9vd&si=_-i-BZBowSIhswTM",
    "Semiconductor Physics and Devices": "https://youtube.com/playlist?list=PLQms29D1RqeKGBEW8La2a7YuN5_4pSV4k&si=Jine6u72kq1fXOfc",
    "Numerical Analysis": "https://youtube.com/playlist?list=PLDea8VeK4MUTppAXQzHBNz3KiyEd9SQms&si=v7TgdXXk1CEGquIA",
    "Electromagnetic Theory I": "https://youtube.com/playlist?list=PLXHedI-xbyr_jDeAYCJjvA9qfLvArL_dI&si=UPsLM7WeBhbPR3F1",
    "Discrete Mathematics": "https://youtube.com/playlist?list=PLl-gb0E4MII28GykmtuBXNUNoej-vY5Rz&si=IAWXtm63Xs4-3xL6",
    "Digital System I": "https://youtube.com/playlist?list=PL-hRFIENVwZwLJsgxxezWS1rjY7aZRXkI&si=Z82Uk3vnuGslX5fV",
    "Circuit Theory II": "https://youtube.com/playlist?list=PL2eW2ex3akpbefoOEDHBi1cBkZ1jMxLjC&si=6_AUU73wddhsWdt-",
}

@bot.message_handler(content_types=['new_chat_members'])
def greet_new_member(message):
    for new_member in message.new_chat_members:
        first_name = new_member.first_name or ""
        last_name = new_member.last_name or ""
        username = f"{first_name} {last_name}".strip()
        bot.send_message(message.chat.id, f"Welcome to the group, {username}! Type /help to get started.")

def bisection_method(func, a, b, tol=0.001):
    steps = []
    if func(a) * func(b) >= 0:
        return "The bisection method cannot be applied due to non existing root", steps

    c = a
    while (b - a) / 2.0 > tol:
        c = (a + b) / 2.0
        steps.append(f"a: {a}, b: {b}, c: {c}, f(c): {func(c)}, error: {(b - a) / 2.0}")
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

    bot.reply_to(message, f"Welcome {username} to MR AWAB study bot!\nUse /help command to see what the bot can do")
    online_users.add(message.chat.id)
    subscribers.add(message.chat.id)
    save_subscribers()

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, HELP)
    online_users.add(message.chat.id)

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    bot.reply_to(message, "Operation cancelled.")
    online_users.add(message.chat.id)

@bot.message_handler(commands=['clear'])
def clear_history(message):
    bot.reply_to(message, "Are you sure you want to clear the history? Type 'yes' to confirm.")
    bot.register_next_step_handler(message, confirm_clear)

def confirm_clear(message):
    if message.text.lower() == 'yes':
        # Clear history logic (if needed)
        bot.reply_to(message, "Chat history cleared.")
    else:
        bot.reply_to(message, "Clear history operation cancelled.")

@bot.message_handler(commands=['bisection'])
def bisection_command(message):
    bot.reply_to(message, "Please send your equation, a, b, and tolerance (optional).")
    bot.register_next_step_handler(message, solve_bisection)

@bot.message_handler(commands=['python'])
def python_command(message):
    bot.reply_to(message, "Please send your Python script to run.")
    bot.register_next_step_handler(message, run_python_script)

def solve_bisection(message):
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
    ast.Module, ast.Expr, ast.Load, ast.Str, ast.Num, ast.BinOp,
    ast.UnaryOp, ast.If, ast.Compare, ast.FunctionDef, ast.Call,
    ast.Assign, ast.AugAssign, ast.Name, ast.Attribute, ast.Subscript,
    ast.Slice, ast.arguments, ast.arg, ast.Return, ast.Pass, ast.Import,
    ast.ImportFrom, ast.alias, ast.Tuple, ast.List, ast.Dict, ast.Set,
    ast.comprehension, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
    ast.BoolOp, ast.And, ast.Or, ast.Not, ast.Break, ast.Continue, ast.For,
    ast.While, ast.IfExp, ast.Lambda, ast.Try, ast.ExceptHandler, ast.Raise,
    ast.FormattedValue, ast.JoinedStr, ast.Constant, ast.Store # Additional nodes for Python 3.6+
}
    
# Store user-defined variables between script executions
user_variables = {}

def run_python_script(message):
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
        thread = threading.Thread(target=execute_script, args=(code, output, safe_globals, safe_locals))
        thread.start()
        thread.join(timeout=5)  # 5-second timeout

# Check for unauthorized access
        for node in ast.walk(tree):
            if type(node) not in ALLOWED_NODES:
                bot.reply_to(message, f"Error: Unauthorized access to {node.__class__.__name__}")
                return

                if isinstance(node, ast.Name) and node.id not in safe_globals and node.id not in dir(__builtins__) and node.id not in user_variables:
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
    bot.send_message(message.chat.id, "Choose a subject to study:", reply_markup=markup)
    online_users.add(message.chat.id)
    subscribers.add(message.chat.id)
    save_subscribers()

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.username == 'mr_awab':  # Replace with your Telegram username
        bot.reply_to(message, "Please send the message to broadcast.")
        bot.register_next_step_handler(message, send_broadcast)
    else:
        bot.reply_to(message, "You are not authorized to send broadcast messages.")

def send_broadcast(message):
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
        "يا فردة", "يا اخونا", "يا شاب", "يا عمك",
        "يافردة",  "يااخونا", "ياشاب", "ياعمك", 'اسمعني', 'اسمع', 'شوفنا'
    ]

    sdword2 = ['عوك', 'عووك', 'عوووك', 'عوووووك']
    sdword3 = ['يازول', 'يازوووول', 'يازوول','يا زول', 'يا زوول', 'يا زووول']
    acknowledgments = ['okey', 'thank you', 'thanks', 'okay', 'thanks a lot', 'قدام ما قصرت', 'قدام', 'ما قصرت', 'طيب']
    Help = ['help', 'مساعده', 'هيلب']
    if any(greeting in message.text.lower() for greeting in greetings):
        response = (
            f"Hi {username}! How can I assist you today?\n"
            "Here are the commands you can use:\n"
            "/start - Start the bot\n"
            "/cancel - Cancel the current operation\n"
            "/help - Show help message\n"
            "/bisection function, a, b, tol - Solve equation using Bisection Method\n"
            "/study - Get study materials\n"
            "Example: /bisection 2**x + 5*x + 2, -1, 0, 0.001"
        )
        bot.reply_to(message, response)
    elif any(ack in message.text.lower() for ack in acknowledgments):
        bot.reply_to(message, f"Okey, {username}, Happy to help!")

    elif any(sd in message.text.lower() for sd in sdwords):
        bot.reply_to(message,"اي جنبك احكي لي عايز شنو \n/start\n/cancel\n/help\n/clear\n/bisection\n/study")
    elif any(sd1 in message.text.lower() for sd1 in sdword2):
        bot.reply_to(message,"عوك في راسك دا بوت قرايه خليك جادي \n/start\n/cancel\n/help\n/clear\n/bisection\n/study")
    elif any(sd2 in message.text.lower() for sd2 in sdword3):
        bot.reply_to(message,"يا دفعة جاي تبقى دافور ولاه شنو هههه\n/start\n/cancel\n/help\n/clear\n/bisection\n/study")
    elif any(help in message.text.lower() for help in Help):
        bot.reply_to(message, HELP)
    else:
        # Check if message is a reply
        if message.reply_to_message:
            # Check if reply is from the bot
            if message.reply_to_message.from_user.id == bot.get_me().id:
                bot.reply_to(message, "Sorry, I didn't understand that. Use /help to see available commands.")
        else:
            # If it's not a reply, it's a direct message
            bot.reply_to(message, "Sorry, I didn't understand that. Use /help to see available commands.")

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
        import time
        time.sleep(10)
