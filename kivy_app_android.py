from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.list import MDList, OneLineListItem
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivymd.toast import toast
from kivy.clock import Clock
import requests
import os
from kivy.utils import platform
from threading import Thread

API_URL = "http://192.168.8.207:5000"

# ----------------- Screens -----------------
class WelcomeScreen(Screen): pass
class SettingsScreen(Screen): pass
class SubjectsScreen(Screen): pass
class LecturesScreen(Screen): pass

# ----------------- App -----------------
class StudyApp(MDApp):
    def build(self):
        self.chat_id = "2134611910"
        self.sm = ScreenManager(transition=SlideTransition())

        # Android-friendly download path
        if platform == "android":
            from android.storage import primary_external_storage_path
            self.download_path = os.path.join(primary_external_storage_path(), "Download")
        else:
            self.download_path = os.path.join(os.getcwd(), "temp_downloads")
        os.makedirs(self.download_path, exist_ok=True)

        # Download progress widget
        self.progress = MDProgressBar(value=0)
        self.progress_label = MDLabel(text="", halign="center")

        self.build_welcome_screen()
        self.build_settings_screen()
        self.build_subjects_screen()
        self.build_lectures_screen()
        return self.sm

    # ----------------- Welcome Screen -----------------
    def build_welcome_screen(self):
        screen = WelcomeScreen(name="welcome")
        layout = MDBoxLayout(orientation="vertical", padding=dp(40), spacing=dp(20),
                             size_hint=(0.3,0.3), pos_hint={"center_x":0.5,"center_y":0.5})
        layout.add_widget(MDRaisedButton(
            text="Welcome! Click to Start", pos_hint={"center_x":0.5,"center_y":0.5},
            on_release=self.go_settings
        ))
        screen.add_widget(layout)
        self.sm.add_widget(screen)

    def go_back(self, screen_name):
        self.sm.current = screen_name

    # ----------------- Settings Screen -----------------
    def go_settings(self, *args):
        self.sm.current = "settings"
    def build_settings_screen(self):
        screen = SettingsScreen(name="settings")
        layout = MDBoxLayout(orientation="vertical", padding=dp(120), spacing=dp(40))
        toolbar = MDTopAppBar(title="Your Settings",
                               left_action_items=[["arrow-left", lambda x:self.go_back("welcome")]],elevation=4)
        layout.add_widget(toolbar)

        self.semester_input = MDTextField(hint_text="Enter semester", pos_hint={"center_x":0.5}, size_hint_x=0.8)
        self.department_input = MDTextField(hint_text="Enter department", pos_hint={"center_x":0.5}, size_hint_x=0.8)
        layout.add_widget(self.semester_input)
        layout.add_widget(self.department_input)

        layout.add_widget(MDRaisedButton(
            text="Submit & Go to Subjects", pos_hint={"center_x":0.5}, on_release=self.submit_settings
        ))
        screen.add_widget(layout)
        self.sm.add_widget(screen)

    def submit_settings(self, *args):
        semester = self.semester_input.text.strip()
        department = self.department_input.text.strip()
        if not semester or not department:
            MDDialog(title="Error", text="Please enter both semester and department").open()
            return
        response = requests.post(f"{API_URL}/set_settings", json={
            "chat_id": self.chat_id,
            "semester": semester,
            "department": department
        })
        if response.status_code == 200:
            self.show_subjects()
            self.sm.current = "subjects"
        else:
            MDDialog(title="Error", text="Failed to save settings").open()

    # ----------------- Subjects -----------------
    def build_subjects_screen(self):
        screen = SubjectsScreen(name="subjects")
        layout = MDBoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(title="Subjects", left_action_items=[["arrow-left", lambda x:self.go_back("settings")]])
        layout.add_widget(toolbar)

        scroll = ScrollView()
        self.subjects_list = MDList()
        scroll.add_widget(self.subjects_list)
        layout.add_widget(scroll)
        screen.add_widget(layout)
        self.sm.add_widget(screen)

    def show_subjects(self):
        self.subjects_list.clear_widgets()
        try: data = requests.get(f"{API_URL}/get_subjects/{self.chat_id}").json()
        except: data = {}
        subjects = data.get("subjects", [])
        if not subjects:
            self.subjects_list.add_widget(OneLineListItem(text="No subjects found"))
            return
        for sub in subjects:
            self.subjects_list.add_widget(
                OneLineListItem(text=sub, on_release=lambda x, s=sub:self.show_lectures(s))
            )

    # ----------------- Lectures -----------------
    def build_lectures_screen(self):
        screen = LecturesScreen(name="lectures")
        layout = MDBoxLayout(orientation="vertical")
        toolbar = MDTopAppBar(title="Lectures", left_action_items=[["arrow-left", lambda x:self.go_back("subjects")]])
        layout.add_widget(toolbar)

        scroll = ScrollView()
        self.lectures_list = MDList()
        scroll.add_widget(self.lectures_list)
        layout.add_widget(scroll)

        # Add progress bar
        layout.add_widget(self.progress_label)
        layout.add_widget(self.progress)

        screen.add_widget(layout)
        self.sm.add_widget(screen)

    def show_lectures(self, subject):
        self.current_subject = subject
        self.lectures_list.clear_widgets()
        try: data = requests.get(f"{API_URL}/get_lectures/{self.chat_id}/{subject}").json()
        except: data = {}
        self.lectures_list_data = data.get("lectures", [])

        for idx, lec in enumerate(self.lectures_list_data):
            self.lectures_list.add_widget(
                OneLineListItem(text=f"{lec['file_name']} ({lec['type']})", on_release=lambda x,i=idx:self.download_lecture_thread(i))
            )
        self.lectures_list.add_widget(
            MDRaisedButton(text="📦 Download All as ZIP", on_release=lambda x:self.download_zip_thread(subject))
        )
        self.sm.current = "lectures"

    # ----------------- Downloads with Animation -----------------
    def download_lecture_thread(self, index):
        Thread(target=self.download_lecture, args=(index,), daemon=True).start()

    def download_zip_thread(self, subject):
        Thread(target=self.download_zip_file, args=(subject,), daemon=True).start()



    # Inside download_lecture
    def download_lecture(self, index):
        lecture = self.lectures_list_data[index]
        ext = {"document": ".pdf", "video": ".mp4", "audio": ".mp3", "photo": ".jpg"}.get(lecture["type"], ".dat")
        path = os.path.join(self.download_path, lecture["file_name"] + ext)

        # Update label safely
        Clock.schedule_once(lambda dt: setattr(self.progress_label, "text", f"Downloading {lecture['file_name']}..."))
        Clock.schedule_once(lambda dt: setattr(self.progress, "value", 0))

        response = requests.post(f"{API_URL}/download_lecture", json={
            "chat_id": self.chat_id, "subject": self.current_subject, "index": index
        }, stream=True)
        total = int(response.headers.get('content-length', 1))
        downloaded = 0
        with open(path, "wb") as f:
            for chunk in response.iter_content(1024 * 256):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Update progress safely
                    Clock.schedule_once(lambda dt, val=(downloaded / total) * 100: setattr(self.progress, "value", val))

        Clock.schedule_once(lambda dt: setattr(self.progress_label, "text", ""))
        Clock.schedule_once(lambda dt: toast(f"Lecture saved at {path}"))

    def download_zip_file(self, subject):
        zip_path = os.path.join(self.download_path, f"{subject}_lectures.zip")
        Clock.schedule_once(lambda dt: setattr(self.progress_label, "text", f"Downloading ZIP {subject}..."))
        Clock.schedule_once(lambda dt: setattr(self.progress, "value", 0))

        response = requests.post(f"{API_URL}/download_zip", json={"chat_id": self.chat_id, "subject": subject},
                                 stream=True)
        total = int(response.headers.get('content-length', 1))
        downloaded = 0
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    Clock.schedule_once(lambda dt, val=(downloaded / total) * 100: setattr(self.progress, "value", val))

        Clock.schedule_once(lambda dt: setattr(self.progress_label, "text", ""))
        Clock.schedule_once(lambda dt: toast(f"ZIP saved at {zip_path}"))


if __name__ == "__main__":
    StudyApp().run()
