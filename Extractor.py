from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib import ITEM_DOCUMENT


def extract_chapters(path:str) -> dict:

    #read the ebook.
    book = epub.read_epub(path)
    #creating a dictionary to store all the chapters.
    chapters = {}
    #iterating through the book.
    for item_id in book.spine:
        #getting the item from the book.
        item = book.get_item_with_id(item_id[0])
        #checking if the item is a document.
        if item == None or item.get_type() != ITEM_DOCUMENT:
            continue

        #filtering out acknolegements and endnotes etc.
        if any(keyword in item.get_name() for keyword in ["chapter", "prologue", "epilogue"]):
            #removing html tags
            soap = BeautifulSoup(item.get_body_content(), 'html.parser')
            #removing images
            for s in soap.find_all("img"):
                s.decompose()
            #storing chapter to dictionary
            chapters[item.get_name()] = "\n\n".join(" ".join(p.get_text().split()) for p in soap.find_all("p") if p.get_text().strip())

    return chapters



