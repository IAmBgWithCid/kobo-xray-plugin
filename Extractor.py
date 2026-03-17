from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
#Add the books path here.
path = "The Way of Kings_ The Stormlight Archive.epub"
#read the ebook.
book = epub.read_epub(path)
#creating a dictionary to store all the chapters.
chapters = {}
#iterating through the book.
for item in book.get_items_of_type(ITEM_DOCUMENT):
    #filtering out acknolegements and endnotes etc.
    if any(keyword in item.get_name() for keyword in ["chapter", "prologue", "epilogue", "part"]):
        #removing html tags
        soap = BeautifulSoup(item.get_body_content(), 'html.parser')
        #removing images
        for s in soap.find_all("img"):
            s.decompose()
        #storing chapter to dictionary
        chapters[item.get_name()] = "\n".join(" ".join(line.split()) for line in soap.get_text().splitlines() if line.strip())

count = 0
# just to verify we go the chapter
for key in chapters.keys():
    print(chapters[key])
    count += 1
    if count >= 1:
        break

