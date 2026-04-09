from calibre.gui2.actions import InterfaceAction
from qt.core import QMessageBox, QProcess, QFileDialog, QMenu, QDialog, QVBoxLayout, QTextEdit, QTextCursor
from calibre.utils.config import JSONConfig
import os

# Create a persistent preferences file specifically for your plugin
prefs = JSONConfig('plugins/koboxray')

# --- THE LIVE PROGRESS TERMINAL ---
class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="Generating X-Ray..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(650, 450)
        self.layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;") # Clean dark-mode terminal look
        
        # Use a monospace font for terminal-like output
        font = self.text_edit.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        self.text_edit.setFont(font)
        
        self.layout.addWidget(self.text_edit)

    def append_log(self, text):
        # Insert text and force the scrollbar to stick to the bottom
        cursor = self.text_edit.textCursor()
        
        # Qt6 strict enum routing
        try:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        except AttributeError:
            # Fallback just in case you are on an older version of Calibre
            cursor.movePosition(QTextCursor.End) 
            
        self.text_edit.setTextCursor(cursor)
        self.text_edit.insertPlainText(text)
        self.text_edit.ensureCursorVisible()


class XRayUI(InterfaceAction):
    name = 'xray'
    action_spec = ('Generate X-Ray', 'book.png', 'Choose a format to generate X-Ray data', 'Ctrl+Shift+X')

    def genesis(self):
        # 1. Create a dynamic dropdown menu attached to the plugin button
        self.format_menu = QMenu(self.gui)
        self.qaction.setMenu(self.format_menu)
        
        # 2. Connect the menu to build itself on the fly just before you open it
        self.format_menu.aboutToShow.connect(self.populate_menu)

        self.engine_process = QProcess(self.gui)
        self.engine_process.finished.connect(self.on_engine_finished)
        
        # 3. Intercept the standard output from main.py and send it to our function
        self.engine_process.readyReadStandardOutput.connect(self.handle_stdout)
        
        self.progress_dialog = None

    def populate_menu(self):
        self.format_menu.clear()
        selected_ids = self.gui.library_view.get_selected_ids()

        if not selected_ids or len(selected_ids) != 1:
            action = self.format_menu.addAction("Please select exactly ONE book")
            action.setEnabled(False)
            return

        book_id = selected_ids[0]
        db = self.gui.current_db.new_api
        formats = [fmt.upper() for fmt in db.formats(book_id)]

        # Strict EPUB-only validation
        valid_formats = [fmt for fmt in formats if fmt == 'EPUB']

        if not valid_formats:
            action = self.format_menu.addAction("No EPUB format found")
            action.setEnabled(False)
            return

        # Generate the clickable option for the EPUB
        for fmt in valid_formats:
            action = self.format_menu.addAction(f"Run X-Ray on {fmt}")
            action.triggered.connect(lambda checked=False, f=fmt, b_id=book_id: self.run_engine(b_id, f))

    def run_engine(self, book_id, target_format):
        self.current_book_id = book_id
        self.target_format = target_format
        db = self.gui.current_db.new_api
        book_title = db.field_for('title', self.current_book_id)
        
        # Fetch the exact absolute path for the chosen format
        self.current_book_path = db.format_abspath(self.current_book_id, self.target_format)

        engine_path = prefs.get('engine_path', None)
        
        if not engine_path or not os.path.exists(engine_path):
            engine_path, _ = QFileDialog.getOpenFileName(
                self.gui, "Locate X-Ray Engine (main.py or compiled .exe)", "", "Executables/Python (*.exe *.py)"
            )
            if not engine_path:
                return 
            prefs['engine_path'] = engine_path 

        if engine_path.endswith('.py'):
            command = "python"
            # CRITICAL FIX: The '-u' flag forces Python to use unbuffered output. 
            # Without this, the UI would stay blank and dump all text at the very end.
            args = ['-u', engine_path, self.current_book_path]
        else:
            command = engine_path
            args = [self.current_book_path]

        # Initialize and show the progress dialog
        self.progress_dialog = ProgressDialog(self.gui, f"Generating X-Ray: {book_title} (EPUB)")
        self.progress_dialog.show()

        # Start the background process
        self.engine_process.start(command, args)

    def handle_stdout(self):
        # This function catches every print() statement from main.py in real-time
        if self.progress_dialog:
            data = self.engine_process.readAllStandardOutput()
            text = bytes(data).decode('utf-8', errors='ignore')
            
            # summary.py uses '\r' to overwrite the progress line. 
            # QTextEdit handles '\r' poorly, so we swap it to a newline for a clean scrolling log.
            if '\r' in text:
                text = text.replace('\r', '\n')
                
            self.progress_dialog.append_log(text)

    def on_engine_finished(self, exit_code, exit_status):
        if exit_code == 0:
            # Dynamically derive the expected output file extension (.epub)
            base_path, ext = os.path.splitext(self.current_book_path)
            expected_output = base_path + "_XRAY" + ext
            
            if os.path.exists(expected_output):
                with open(expected_output, 'rb') as f:
                    self.gui.current_db.new_api.add_format(self.current_book_id, self.target_format, f, run_hooks=True)
                
                os.remove(expected_output)
                
                # Close the progress window automatically on a clean success
                if self.progress_dialog:
                    self.progress_dialog.accept()
                    
                QMessageBox.information(self.gui, 'Success', 'X-Ray data injected! The EPUB in your library has been updated.')
            else:
                if self.progress_dialog:
                    self.progress_dialog.append_log("\n\nERROR: Engine finished, but output file is missing.")
                QMessageBox.warning(self.gui, 'Error', 'Engine finished, but the output file is missing.')
        else:
            error_msg = str(self.engine_process.readAllStandardError(), 'utf-8')
            if self.progress_dialog:
                self.progress_dialog.append_log(f"\n\nCRITICAL ERROR:\n{error_msg}")
            QMessageBox.critical(self.gui, 'Engine Error', f'Critical error:\n\n{error_msg}')