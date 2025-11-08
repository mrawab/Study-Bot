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
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivymd.toast import toast
import requests
import os

API_URL = "http://192.168.8.207:5000"

# ----------------- Screens -----------------
class WelcomeScreen(Screen):
    pass

class SettingsScreen(Screen):
    pass

class SubjectsScreen(Screen):
    pass

class LecturesScreen(Screen):
    pass

# ----------------- App -----------------
class StudyApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.download_path = "C:/Users/Public/Downloads"  # default starting folder

    def build(self):
        self.chat_id = "2134611910"
        self.download_path = os.path.join(os.getcwd(), "temp_downloads")
        os.makedirs(self.download_path, exist_ok=True)

        self.sm = ScreenManager(transition=SlideTransition())

        self.build_welcome_screen()
        self.build_settings_screen()
        self.build_subjects_screen()
        self.build_lectures_screen()

        return self.sm

    # ----------------- Welcome Screen -----------------
    def build_welcome_screen(self):
        screen = WelcomeScreen(name="welcome")
        layout = MDBoxLayout(orientation="vertical", padding=dp(40), spacing=dp(20))
        layout.size_hint = (0.9, 0.9)
        layout.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        layout.add_widget(MDRaisedButton(
            text="Welcome! Click to Start",
            pos_hint={"center_x": 0.5},
            on_release=self.go_settings
        ))

        screen.add_widget(layout)
        self.sm.add_widget(screen)

    def go_settings(self, *args):
        self.sm.current = "settings"

    # ----------------- Settings Screen -----------------
    def build_settings_screen(self):
        screen = SettingsScreen(name="settings")
        layout = MDBoxLayout(orientation="vertical", padding=dp(20), spacing=dp(20))

        toolbar = MDTopAppBar(
            title="Your Settings",
            left_action_items=[["arrow-left", lambda x: self.go_back("welcome")]]
        )
        layout.add_widget(toolbar)

        # Semester input
        self.semester_input = MDTextField(
            hint_text="Enter semester",
            pos_hint={"center_x": 0.5},
            size_hint_x=0.8
        )
        layout.add_widget(self.semester_input)

        # Department input
        self.department_input = MDTextField(
            hint_text="Enter department",
            pos_hint={"center_x": 0.5},
            size_hint_x=0.8
        )
        layout.add_widget(self.department_input)

        # Submit button
        layout.add_widget(MDRaisedButton(
            text="Submit & Go to Subjects",
            pos_hint={"center_x": 0.5},
            on_release=self.submit_settings
        ))

        screen.add_widget(layout)
        self.sm.add_widget(screen)

    # ----------------- Subjects Screen -----------------
    def build_subjects_screen(self):
        screen = SubjectsScreen(name="subjects")
        layout = MDBoxLayout(orientation="vertical")

        toolbar = MDTopAppBar(
            title="Subjects",
            left_action_items=[["arrow-left", lambda x: self.go_back("settings")]]
        )
        layout.add_widget(toolbar)

        scroll = ScrollView()
        self.subjects_list = MDList()
        scroll.add_widget(self.subjects_list)
        layout.add_widget(scroll)

        screen.add_widget(layout)
        self.sm.add_widget(screen)

    # ----------------- Lectures Screen -----------------
    def build_lectures_screen(self):
        screen = LecturesScreen(name="lectures")
        layout = MDBoxLayout(orientation="vertical")

        toolbar = MDTopAppBar(
            title="Lectures",
            left_action_items=[["arrow-left", lambda x: self.go_back("subjects")]]
        )
        layout.add_widget(toolbar)

        scroll = ScrollView()
        self.lectures_list = MDList()
        scroll.add_widget(self.lectures_list)
        layout.add_widget(scroll)

        screen.add_widget(layout)
        self.sm.add_widget(screen)

    # ----------------- Navigation -----------------
    def go_back(self, screen_name):
        self.sm.current = screen_name

    # ----------------- Submit Settings -----------------
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
    def show_subjects(self):
        self.subjects_list.clear_widgets()
        response = requests.get(f"{API_URL}/get_subjects/{self.chat_id}")
        try:
            data = response.json()
        except Exception:
            data = {}
        subjects = data.get("subjects", [])

        if not subjects:
            self.subjects_list.add_widget(OneLineListItem(text="No subjects found"))
            return

        for sub in subjects:
            item = OneLineListItem(text=sub, on_release=lambda x, s=sub: self.show_lectures(s))
            self.subjects_list.add_widget(item)

    # ----------------- Lectures -----------------
    def show_lectures(self, subject):
        self.current_subject = subject
        self.lectures_list.clear_widgets()

        response = requests.get(f"{API_URL}/get_lectures/{self.chat_id}/{subject}")
        data = response.json()
        self.lectures_list_data = data.get("lectures", [])

        for idx, lec in enumerate(self.lectures_list_data):
            item = OneLineListItem(
                text=f"{lec['file_name']} ({lec['type']})",
                on_release=lambda x, i=idx: self.choose_save_location(i)
            )
            self.lectures_list.add_widget(item)

        # Download all button
        self.lectures_list.add_widget(MDRaisedButton(
            text="📦 Download All as ZIP",
            on_release=lambda x: self.download_zip(subject)
        ))

        self.sm.current = "lectures"

    # ----------------- File Manager -----------------
    def choose_save_location(self, index):
        self.selected_index = index
        self.open_file_manager(self.download_path)

    def download_zip(self, subject):
        self.downloading_zip_subject = subject
        self.open_file_manager(self.download_path)

    def open_file_manager(self, start_path):
        """
        Show MDFileManager with a current path label
        """
        layout = MDBoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        self.current_path_label = MDLabel(text=start_path, halign="center", size_hint_y=None, height=dp(30))
        layout.add_widget(self.current_path_label)

        self.file_manager = MDFileManager(
            exit_manager=self.exit_manager,
            select_path=self.select_path,
            preview=True
        )
        self.file_manager.show(start_path)

    def select_path(self, folder_path):
        self.file_manager.close()
        toast(f"Selected folder: {folder_path}")

        # Individual lecture
        if hasattr(self, "selected_index"):
            lecture = self.lectures_list_data[self.selected_index]
            ext = {"document": ".pdf", "video": ".mp4", "audio": ".mp3", "photo": ".jpg"}.get(lecture["type"], ".dat")
            file_name = f"{lecture['file_name']}{ext}"
            full_path = os.path.join(folder_path, file_name)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            self.download_lecture(self.current_subject, self.selected_index, full_path)
            del self.selected_index

        # ZIP download
        elif hasattr(self, "downloading_zip_subject"):
            zip_name = f"{self.downloading_zip_subject}_lectures.zip"
            full_path = os.path.join(folder_path, zip_name)
            self.download_zip_file(self.downloading_zip_subject, full_path)
            del self.downloading_zip_subject

    def exit_manager(self, *args):
        self.file_manager.close()

    # ----------------- Downloads -----------------
    def download_lecture(self, subject, index, full_path):
        response = requests.post(f"{API_URL}/download_lecture", json={
            "chat_id": self.chat_id,
            "subject": subject,
            "index": index
        }, stream=True)

        if response.status_code == 200:
            with open(full_path, "wb") as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
            toast(f"Lecture saved at:\n{full_path}")
        else:
            toast(f"Failed to download lecture (status {response.status_code})")

    def download_zip_file(self, subject, full_path):
        response = requests.post(
            f"{API_URL}/download_zip",
            json={"chat_id": self.chat_id, "subject": subject},
            stream=True
        )

        if response.status_code == 200:
            with open(full_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            MDDialog(title="Downloaded", text=f"ZIP saved at:\n{full_path}").open()
        else:
            MDDialog(title="Error", text=f"Failed to download ZIP (status {response.status_code})").open()


if __name__ == "__main__":
    StudyApp().run()
