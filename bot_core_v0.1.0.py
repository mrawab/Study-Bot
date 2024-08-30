import telebot
import sympy as sp
import signal
import sys

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot = telebot.TeleBot('TELEGRAM_BOT_API')
HELP = "This bot solves equations using the Bisection Method.\n Commands:\n /start - Start the bot\n /cancel - Cancel the current operation\n /help - Show this help message\n Usage: Use /bisection command followed by the function, a, b, and tolerance.\n Example: /bisection 2**x + 5*x + 2, -1, 0, 0.001\n **patch 0.2 now the bot support greeting, acknowledgments, some Sudanese words : اسمعني، اسمع، شوفنا، قدام ما قصرت\n you can now reach help by typing help, هيلب, مساعده**"

chat_history = {}

def bisection_method(func, a, b, tol):
    steps = []
    if func(a) * func(b) >= 0:
        return "The bisection method cannot be applied.", steps

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

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, "Welcome to MR AWAB Bisection Method Solver Bot!\n"
        "Use /bisection to solve equations using the Bisection Method.\n"
        "Send a message in the format: function, a, b, tol\n"
        "Example: 2**x + 5*x + 2, -1, 0, 0.001"
    )
    chat_history[message.chat.id] = []

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, HELP)
    if message.chat.id not in chat_history:
        chat_history[message.chat.id] = []
    chat_history[message.chat.id].append(message.text)

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    bot.reply_to(message, "Operation cancelled.")
    if message.chat.id not in chat_history:
        chat_history[message.chat.id] = []
    chat_history[message.chat.id].append(message.text)

@bot.message_handler(commands=['clear'])
def clear_history(message):
    bot.reply_to(message, "Are you sure you want to clear the history? Type 'yes' to confirm.")
    bot.register_next_step_handler(message, confirm_clear)

def confirm_clear(message):
    if message.text.lower() == 'yes':
        chat_history[message.chat.id] = []
        bot.reply_to(message, "Chat history cleared.")
    else:
        bot.reply_to(message, "Clear history operation cancelled.")

@bot.message_handler(commands=['bisection'])
def solve_bisection(message):
    try:
        data = message.text[len('/bisection '):].split(',')
        func_str = data[0].strip()
        a = float(data[1].strip())
        b = float(data[2].strip())
        tol = float(data[3].strip())

        x = sp.symbols('x')
        func = sp.lambdify(x, sp.sympify(func_str))

        result, steps = bisection_method(func, a, b, tol)

        steps_str = "\n".join(steps)

        bot.reply_to(message, f"Root = {result}\nSteps:\n{steps_str}")
        bot.reply_to(message, "Success")
        if message.chat.id not in chat_history:
            chat_history[message.chat.id] = []
        chat_history[message.chat.id].append(message.text)
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")
        if message.chat.id not in chat_history:
            chat_history[message.chat.id] = []
        chat_history[message.chat.id].append(message.text)

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    greetings = ['hi', 'hello', 'hey', 'greetings','اسمعني', 'اسمع', 'شوفنا']
    acknowledgments = ['okey', 'thank you', 'thanks', 'okay', 'thanks a lot', 'قدام ما قصرت', 'قدام', 'ما قصرت']
    Help = ['help', 'مساعده', 'هيلب']
    if any(greeting in message.text.lower() for greeting in greetings):
        username = message.from_user.username
        response = (
            f"Hi {username}! How can I assist you today?\n"
            "Here are the commands you can use:\n"
            "/start - Start the bot\n"
            "/cancel - Cancel the current operation\n"
            "/help - Show help message\n"
            "/bisection function, a, b, tol - Solve equation using Bisection Method\n"
            "Example: /bisection 2**x + 5*x + 2, -1, 0, 0.001"
        )
        bot.reply_to(message, response)
    elif any(ack in message.text.lower() for ack in acknowledgments):
        username = message.from_user.username
        bot.reply_to(message, f"Okey, my {username}. Happy to help!")
    elif any(help in message.text.lower() for help in Help):
        bot.reply_to(message, HELP)
    else:
        bot.reply_to(message, "Sorry, I didn't understand that. Use /help to see available commands.")

    if message.chat.id not in chat_history:
        chat_history[message.chat.id] = []
    chat_history[message.chat.id].append(message.text)

# Function to handle unexpected bot shutdown and notify users
def notify_users_offline():
    for chat_id in chat_history:
        try:
            bot.send_message(chat_id, "I am currently offline, as soon as I'm back I will respond")
        except:
            pass

def signal_handler(sig, frame):
    notify_users_offline()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

bot.polling()