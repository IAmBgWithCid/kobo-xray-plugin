import json
import re
import posixpath
from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT

def inject_xray_data(epub_path, json_path, output_epub_path):
    print(f"Opening {epub_path} for X-Ray injection (Standard EPUB Mode)...")
    book = epub.read_epub(epub_path)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        xray_list = json.load(f)
    
    xray_dict = {item['entity'].lower(): item for item in xray_list}
    sorted_entities = sorted(xray_dict.keys(), key=len, reverse=True)
    
    escaped_entities = [re.escape(ent) for ent in sorted_entities]
    regex_pattern = r'\b(' + '|'.join(escaped_entities) + r')\b'
    mega_regex = re.compile(regex_pattern, re.IGNORECASE)

    print("Generating pop-up footnote dictionary...")
    
    footnotes_html = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">\n'
        '<head><title>X-Ray Summaries</title></head>\n'
        '<body>\n'
        '<h1>X-Ray Entity Glossary</h1>\n'
    )
    
    for entity in sorted_entities:
        data = xray_dict[entity]
        safe_id = entity.replace(" ", "_").replace("'", "")
        footnotes_html += (
            f'<aside epub:type="footnote" id="{safe_id}">\n'
            f'  <b>{data["entity"].title()}</b>\n'
            f'  <p>{data["summary"]}</p>\n'
            f'</aside>\n'
        )
    footnotes_html += '</body>\n</html>'
    
    # CRITICAL FIX 4: uid added to prevent ebooklib crash during zip
    footnote_item = epub.EpubHtml(
        uid='xray_footnotes',
        title='X-Ray Summaries', 
        file_name='xray_footnotes.xhtml', 
        lang='en'
    )
    footnote_item.set_content(footnotes_html.encode('utf-8'))
    book.add_item(footnote_item)
    
    # CRITICAL FIX 1: Add the new file to the book's official spine
    book.spine.append(footnote_item)

    print("Scanning and injecting links into chapters...")
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        doc_path = item.get_name()
        
        if doc_path.endswith('xray_footnotes.xhtml'):
            continue
        
        doc_dir = posixpath.dirname(doc_path)
        rel_footnotes_path = posixpath.relpath('xray_footnotes.xhtml', doc_dir)

        def dynamic_replace(match):
            matched_text = match.group(0)
            entity_key = matched_text.lower()
            safe_id = entity_key.replace(" ", "_").replace("'", "")
            
            # CRITICAL FIX 3: Added white-space: nowrap
            return (
                f'<a href="{rel_footnotes_path}#{safe_id}" epub:type="noteref" '
                f'style="color: inherit !important; text-decoration: none !important; border: none !important; white-space: nowrap !important;">'
                f'{matched_text}'
                f'</a>'
            )
            
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        modified = False

        # CRITICAL FIX 2: Inject the EPUB3 namespace
        html_tag = soup.find('html')
        if html_tag and not html_tag.has_attr('xmlns:epub'):
            html_tag['xmlns:epub'] = "http://www.idpf.org/2007/ops"
            modified = True

        body = soup.find('body')
        target_container = body if body else soup

        for text_node in target_container.find_all(string=True):
            if text_node.parent.name in ['a', 'script', 'style', 'title', 'h1', 'h2']:
                continue
            
            original_text = str(text_node)
            new_text = mega_regex.sub(dynamic_replace, original_text)
            
            if new_text != original_text:
                new_html = BeautifulSoup(new_text, 'html.parser')
                for child in new_html.contents[:]: 
                    text_node.insert_before(child)
                text_node.extract()
                modified = True
                
        if modified:
            item.set_content(str(soup).encode('utf-8'))

    # --- CRITICAL FIX 5: ebooklib TOC Bug Workaround ---
    # ebooklib often reads existing TOC items with missing UIDs, but strictly 
    # requires UIDs to write them back out. This sweeps and patches the broken TOC.
    def fix_toc_uids(toc):
        for el in toc:
            if isinstance(el, (tuple, list)):
                section, sub_toc = el[0], el[1]
                if getattr(section, 'uid', None) is None:
                    section.uid = f"uid_{id(section)}"
                fix_toc_uids(sub_toc)
            else:
                if getattr(el, 'uid', None) is None:
                    el.uid = f"uid_{id(el)}"

    fix_toc_uids(book.toc)
    # ---------------------------------------------------

    print(f"Saving finalized X-Ray EPUB to {output_epub_path}...")
    epub.write_epub(output_epub_path, book)
    print("Injection Complete!")