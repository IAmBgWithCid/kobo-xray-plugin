from calibre.gui2.actions import InterfaceAction
from qt.core import (QMessageBox, QProcess, QFileDialog, QDialog, QVBoxLayout, 
                     QHBoxLayout, QPushButton, QLabel, QComboBox, QTabWidget, 
                     QWidget, QTextEdit, QTextCursor, Qt)
from calibre.utils.config import JSONConfig
import os
import tempfile
import urllib.request
import urllib.error

# Import our new pure-Python injector
try:
    from calibre_plugins.kobo_xray.injector import process_sigil_and_inject
except ImportError:
    # Fallback for local testing outside calibre plugin environment if needed
    try:
        from .injector import process_sigil_and_inject
    except ImportError:
        pass


prefs = JSONConfig('plugins/koboxray')

# --- THE LIVE PROGRESS TERMINAL ---
class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="Processing..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(650, 450)
        self.layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        
        font = self.text_edit.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        self.text_edit.setFont(font)
        
        self.layout.addWidget(self.text_edit)

    def append_log(self, text):
        cursor = self.text_edit.textCursor()
        try:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        except AttributeError:
            cursor.movePosition(QTextCursor.End) 
            
        self.text_edit.setTextCursor(cursor)
        self.text_edit.insertPlainText(text)
        self.text_edit.ensureCursorVisible()


# --- THE MAIN HUB DIALOG ---
class XRayHubDialog(QDialog):
    def __init__(self, gui, book_id, book_title, epub_path):
        super().__init__(gui)
        self.gui = gui
        self.book_id = book_id
        self.book_title = book_title
        self.epub_path = epub_path
        
        self.setWindowTitle(f"Kobo X-Ray Manager: {self.book_title}")
        self.resize(500, 300)
        self.layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # TAB 1: ARCHIVE (Cloud / Local File)
        self.tab_archive = QWidget()
        self.setup_archive_tab()
        self.tabs.addTab(self.tab_archive, "Archive (Fetch)")
        
        # TAB 2: FORGE (Local Engine)
        self.tab_forge = QWidget()
        self.setup_forge_tab()
        self.tabs.addTab(self.tab_forge, "Forge (Generate)")

        # Result state
        self.success = False

    def setup_archive_tab(self):
        layout = QVBoxLayout(self.tab_archive)
        
        layout.addWidget(QLabel("<h2>Archive</h2>"))
        layout.addWidget(QLabel("Download a pre-generated .sigil file from the Supabase Vault, or load one from your computer."))
        layout.addSpacing(20)
        
        btn_cloud = QPushButton("Fetch from Cloud (Supabase)")
        btn_cloud.setFixedHeight(40)
        btn_cloud.clicked.connect(self.fetch_from_cloud)
        layout.addWidget(btn_cloud)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("— OR —", alignment=Qt.AlignmentFlag.AlignCenter))
        layout.addSpacing(10)
        
        btn_local = QPushButton("Load Local .sigil File")
        btn_local.setFixedHeight(40)
        btn_local.clicked.connect(self.load_local_sigil)
        layout.addWidget(btn_local)
        
        layout.addStretch()

    def setup_forge_tab(self):
        layout = QVBoxLayout(self.tab_forge)
        
        layout.addWidget(QLabel("<h2>Forge</h2>"))
        layout.addWidget(QLabel("Generate a new X-Ray locally using the X-Ray Engine and GPU acceleration."))
        layout.addSpacing(10)
        
        # Model Selection
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("AI Model:"))
        self.model_combo = QComboBox()
        # Add popular Ollama models
        self.model_combo.addItems(["llama3", "llama3:8b", "qwen3.5:9b", "mistral", "gemma", "phi3"])
        # Restore previous selection
        last_model = prefs.get('last_model', 'llama3')
        index = self.model_combo.findText(last_model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        h_layout.addWidget(self.model_combo)
        layout.addLayout(h_layout)
        
        layout.addSpacing(20)
        
        btn_generate = QPushButton("Generate X-Ray")
        btn_generate.setFixedHeight(40)
        btn_generate.setStyleSheet("font-weight: bold;")
        btn_generate.clicked.connect(self.generate_locally)
        layout.addWidget(btn_generate)
        
        layout.addStretch()
        
        btn_config = QPushButton("Configure Engine Path")
        btn_config.clicked.connect(self.configure_engine)
        layout.addWidget(btn_config)

    def fetch_from_cloud(self):
        import uuid
        import urllib.parse
        
        # 1. Calculate the expected UUID
        NAMESPACE_SIGIL = uuid.uuid5(uuid.NAMESPACE_DNS, "sigil.community.project")
        base_path, _ = os.path.splitext(self.epub_path)
        filename_title = os.path.basename(base_path).replace("_", " ").title()
        book_uuid = str(uuid.uuid5(NAMESPACE_SIGIL, filename_title.lower().strip()))
        
        # 2. Get Supabase URL and Key from .env if possible
        supabase_url = "https://ysdvrvizgetheidlnavv.supabase.co"
        supabase_key = "" # We'll try to find this
        
        engine_path = prefs.get('engine_path', None)
        if engine_path and os.path.exists(engine_path):
            # Check for .env in the engine directory OR one level up (if pointing to dist/XRayEngine/XRayEngine.exe)
            search_dirs = [os.path.dirname(engine_path), os.path.dirname(os.path.dirname(engine_path))]
            for s_dir in search_dirs:
                env_path = os.path.join(s_dir, '.env')
                if os.path.exists(env_path):
                    try:
                        with open(env_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith('SUPABASE_URL='):
                                    supabase_url = line.split('=', 1)[1].strip().strip('"\'')
                                elif line.startswith('SUPABASE_KEY='):
                                    supabase_key = line.split('=', 1)[1].strip().strip('"\'')
                        break # Found the .env
                    except Exception:
                        pass
        
        # 3. Construct URL
        supabase_url = supabase_url.rstrip('/')
        # Use quote to be safe, although UUIDs are safe
        safe_filename = urllib.parse.quote(f"{book_uuid}.sigil")
        download_url = f"{supabase_url}/storage/v1/object/public/sigil-vault/{safe_filename}"
        
        print(f"KoboXRay: Attempting cloud fetch from {download_url}")
        
        # 4. Download and process
        try:
            headers = {
                'User-Agent': 'KoboXRayPlugin/1.0',
            }
            # Even for public buckets, Supabase sometimes prefers the apikey
            if supabase_key:
                headers['apikey'] = supabase_key
                headers['Authorization'] = f'Bearer {supabase_key}'
                
            req = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                sigil_data = response.read()
                
            with tempfile.NamedTemporaryFile(delete=False, suffix='.sigil', mode='wb') as temp_sigil:
                temp_sigil.write(sigil_data)
                temp_sigil_path = temp_sigil.name
                
            print(f"KoboXRay: Downloaded {len(sigil_data)} bytes. Injecting...")
            self.process_sigil_file(temp_sigil_path)
            os.remove(temp_sigil_path)
            
            self.success = True
            self.accept()
            
        except urllib.error.HTTPError as e:
            print(f"KoboXRay: HTTP Error {e.code}: {e.reason}")
            if e.code == 404:
                QMessageBox.warning(self, "Not Found", f"No X-Ray data found in the Archive for this book.\n(Checked ID: {book_uuid})")
            elif e.code == 400:
                QMessageBox.critical(self, "Download Error", f"Bad Request (400). This usually means the URL or Bucket name is incorrect.\n\nURL: {download_url}")
            else:
                QMessageBox.critical(self, "Download Error", f"Failed to fetch from Cloud: {e.code} {e.reason}")
        except Exception as e:
            print(f"KoboXRay: Unexpected Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred:\n\n{str(e)}")

    def load_local_sigil(self):
        sigil_path, _ = QFileDialog.getOpenFileName(
            self, "Select .sigil file", "", "Sigil Files (*.sigil)"
        )
        if not sigil_path:
            return
            
        try:
            self.process_sigil_file(sigil_path)
            self.success = True
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Injection Error", f"Failed to process .sigil file:\n\n{str(e)}")

    def configure_engine(self):
        engine_path, _ = QFileDialog.getOpenFileName(
            self, "Locate X-Ray Engine (main.py or compiled .exe)", "", "Executables/Python (*.exe *.py)"
        )
        if engine_path:
            prefs['engine_path'] = engine_path 
            QMessageBox.information(self, "Success", "Engine path updated.")

    def generate_locally(self):
        engine_path = prefs.get('engine_path', None)
        if not engine_path or not os.path.exists(engine_path):
            QMessageBox.warning(self, "Missing Engine", "Please configure the Engine path first.")
            self.configure_engine()
            return
            
        selected_model = self.model_combo.currentText()
        prefs['last_model'] = selected_model
            
        self.run_engine_process(engine_path, selected_model)

    def run_engine_process(self, engine_path, model):
        self.engine_process = QProcess(self)
        
        if engine_path.endswith('.py'):
            command = "python"
            args = ['-u', engine_path, self.epub_path, '--model', model]
        else:
            command = engine_path
            args = [self.epub_path, '--model', model]

        self.progress_dialog = ProgressDialog(self, f"Generating X-Ray: {self.book_title}")
        
        self.engine_process.readyReadStandardOutput.connect(self.handle_stdout)
        self.engine_process.finished.connect(self.on_engine_finished)
        
        self.progress_dialog.show()
        
        # Set working directory to the engine folder so it finds its .env
        engine_dir = os.path.dirname(os.path.abspath(engine_path))
        self.engine_process.setWorkingDirectory(engine_dir)
        
        self.engine_process.start(command, args)

    def handle_stdout(self):
        if self.progress_dialog:
            data = self.engine_process.readAllStandardOutput()
            text = bytes(data).decode('utf-8', errors='ignore')
            if '\r' in text:
                text = text.replace('\r', '\n')
            self.progress_dialog.append_log(text)

    def on_engine_finished(self, exit_code, exit_status):
        if exit_code == 0:
            # The engine produces an _XRAY.sigil file next to the epub
            base_path, _ = os.path.splitext(self.epub_path)
            expected_sigil = base_path + "_XRAY.sigil"
            
            if os.path.exists(expected_sigil):
                try:
                    self.process_sigil_file(expected_sigil)
                    os.remove(expected_sigil) # Clean up the temp sigil
                    
                    if self.progress_dialog:
                        self.progress_dialog.accept()
                        
                    self.success = True
                    self.accept()
                except Exception as e:
                    if self.progress_dialog:
                        self.progress_dialog.append_log(f"\n\nINJECTION ERROR:\n{str(e)}")
                    QMessageBox.critical(self, "Injection Error", f"Failed to inject generated file:\n\n{str(e)}")
            else:
                if self.progress_dialog:
                    self.progress_dialog.append_log("\n\nERROR: Engine finished, but .sigil output file is missing.")
                QMessageBox.warning(self, 'Error', 'Engine finished, but the .sigil file is missing.')
        else:
            error_msg = str(self.engine_process.readAllStandardError(), 'utf-8')
            if self.progress_dialog:
                self.progress_dialog.append_log(f"\n\nCRITICAL ERROR:\n{error_msg}")

    def process_sigil_file(self, sigil_path):
        """Unpacks the .sigil and injects it into the EPUB."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_epub = os.path.join(temp_dir, "temp.epub")
            
            # 1. Unpack Sigil & Inject into EPUB (pure Python + bs4)
            process_sigil_and_inject(sigil_path, self.epub_path, temp_epub)
            
            # 2. Overwrite original EPUB in Calibre DB
            with open(temp_epub, 'rb') as f:
                self.gui.current_db.new_api.add_format(self.book_id, 'EPUB', f, run_hooks=True)


class XRayUI(InterfaceAction):
    name = 'xray'
    action_spec = ('Kobo X-Ray', 'book.png', 'Manage Kobo X-Ray data (Cloud/Local)', 'Ctrl+Shift+X')

    def genesis(self):
        # We don't need a menu anymore, just click the button to open the Hub
        self.qaction.triggered.connect(self.open_hub)

    def open_hub(self):
        selected_ids = self.gui.library_view.get_selected_ids()

        if not selected_ids or len(selected_ids) != 1:
            QMessageBox.warning(self.gui, "Selection Error", "Please select exactly ONE book.")
            return

        book_id = selected_ids[0]
        db = self.gui.current_db.new_api
        formats = [fmt.upper() for fmt in db.formats(book_id)]

        if 'EPUB' not in formats:
            QMessageBox.warning(self.gui, "Format Error", "No EPUB format found for this book.")
            return

        book_title = db.field_for('title', book_id)
        epub_path = db.format_abspath(book_id, 'EPUB')

        # Open the Main UI Dialog
        dialog = XRayHubDialog(self.gui, book_id, book_title, epub_path)
        if dialog.exec():
            # If exec() returns True (success = True), show a success message
            if dialog.success:
                QMessageBox.information(self.gui, 'Success', 'X-Ray data injected! The EPUB in your library has been updated.')