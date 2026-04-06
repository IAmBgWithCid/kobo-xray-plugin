from calibre.gui2.actions import InterfaceAction
from qt.core import QMessageBox

class XRayUI(InterfaceAction):
    # Matches the new ID perfectly
    name = 'xray_generator'
    action_spec = ('Generate X-Ray', 'book.png', 'Click to generate Kobo X-Ray data', 'Ctrl+Shift+X')

    def genesis(self):
        self.qaction.triggered.connect(self.button_clicked)

    def button_clicked(self):
        selected_ids = self.gui.library_view.get_selected_ids()
        
        if not selected_ids or len(selected_ids) != 1:
            QMessageBox.warning(self.gui, 'Selection Error', 'Please select exactly ONE book to generate an X-Ray.')
            return

        book_id = selected_ids[0]
        db = self.gui.current_db.new_api
        
        title = db.field_for('title', book_id)
        epub_path = db.format_abspath(book_id, 'EPUB')

        if not epub_path:
            QMessageBox.warning(self.gui, 'Format Error', f'"{title}" does not have an EPUB format downloaded.')
            return

        QMessageBox.information(self.gui, 'Target Acquired!', f'Ready to send this to the engine:\n\n{title}\n\nPath:\n{epub_path}')