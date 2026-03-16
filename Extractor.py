from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib import ITEM_DOCUMENT

path = "The Way of Kings_ The Stormlight Archive.epub"

book = epub.read_epub(path)

chapters = {}

for item in book.get_items_of_type(ITEM_DOCUMENT):
    if any(keyword in item.get_name() for keyword in ["chapter", "prologue", "epilogue", "part"]):
        soap = BeautifulSoup(item.get_body_content(), 'html.parser')
        chapters[item.get_name()] = soap.get_text()

count = 0

for key in chapters.keys():
    print(chapters[key])
    count += 1
    if count >= 1:
        break

