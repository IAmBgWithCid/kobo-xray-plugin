import os
import zlib
import hashlib
import struct
import tempfile
import zipfile
import shutil
import json
import re
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

def unpack_sigil(sigil_path: str):
    """
    Unpacks a .sigil file and returns the parsed JSON data.
    """
    with open(sigil_path, "rb") as f:
        magic = f.read(4)
        if magic != b"SIGL":
            raise ValueError("Not a valid .sigil file (invalid magic number)")
            
        version = struct.unpack("B", f.read(1))[0]
        if version != 1:
            raise ValueError(f"Unsupported .sigil version: {version}")
            
        expected_checksum = f.read(32)
        compressed_payload = f.read()
        
        # Verify checksum
        actual_checksum = hashlib.sha256(compressed_payload).digest()
        if expected_checksum != actual_checksum:
            raise ValueError("Checksum mismatch! The .sigil file is corrupted.")
            
        # Decompress and load JSON
        json_bytes = zlib.decompress(compressed_payload)
        return json.loads(json_bytes.decode('utf-8'))

def inject_xray_footnotes(epub_path: str, xray_list: list, output_epub_path: str):
    """
    Injects the X-Ray footnotes into the EPUB using raw zipfile and bs4.
    This replaces ebooklib to remain lightweight for the Calibre plugin.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. Unzip EPUB
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # 2. Locate the OPF file from META-INF/container.xml
        container_path = os.path.join(temp_dir, 'META-INF', 'container.xml')
        if not os.path.exists(container_path):
            raise FileNotFoundError("Invalid EPUB: META-INF/container.xml missing")
            
        ns_container = {'n': 'urn:oasis:names:tc:opendocument:xmlns:container'}
        tree = ET.parse(container_path)
        rootf = tree.find('.//n:rootfile', ns_container)
        if rootf is None:
            raise ValueError("Invalid EPUB: no rootfile found in container.xml")
            
        opf_rel_path = rootf.get('full-path')
        opf_full_path = os.path.join(temp_dir, opf_rel_path)
        opf_dir = os.path.dirname(opf_full_path)
        
        # 3. Parse OPF to find html files and add footnote file
        ns_opf = {'opf': 'http://www.idpf.org/2007/opf'}
        ET.register_namespace('', 'http://www.idpf.org/2007/opf')
        opf_tree = ET.parse(opf_full_path)
        opf_root = opf_tree.getroot()
        
        manifest = opf_root.find('opf:manifest', ns_opf)
        spine = opf_root.find('opf:spine', ns_opf)
        
        if manifest is None or spine is None:
            raise ValueError("Invalid OPF: missing manifest or spine")
            
        # Find all HTML/XHTML items in manifest
        html_items = {}
        for item in manifest.findall('opf:item', ns_opf):
            mt = item.get('media-type')
            if mt in ['application/xhtml+xml', 'text/html']:
                html_items[item.get('id')] = item.get('href')
                
        # 4. Generate footnote HTML
        xray_dict = {item['entity'].lower(): item for item in xray_list}
        sorted_entities = sorted(xray_dict.keys(), key=len, reverse=True)
        
        escaped_entities = [re.escape(ent) for ent in sorted_entities]
        regex_pattern = r'\b(' + '|'.join(escaped_entities) + r')\b'
        mega_regex = re.compile(regex_pattern, re.IGNORECASE)
        
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
        
        # Save footnote HTML
        footnote_filename = 'xray_footnotes.xhtml'
        footnote_full_path = os.path.join(opf_dir, footnote_filename)
        with open(footnote_full_path, 'wb') as f:
            f.write(footnotes_html.encode('utf-8'))
            
        # Update OPF manifest & spine
        footnote_id = 'xray_footnotes_id'
        new_item = ET.SubElement(manifest, 'item')
        new_item.set('id', footnote_id)
        new_item.set('href', footnote_filename)
        new_item.set('media-type', 'application/xhtml+xml')
        
        new_itemref = ET.SubElement(spine, 'itemref')
        new_itemref.set('idref', footnote_id)
        
        opf_tree.write(opf_full_path, encoding='utf-8', xml_declaration=True)
        
        # 5. Scan and inject links into all HTML chapters
        # Determine relative path from chapter to footnote file (often same dir)
        
        for item_id, href in html_items.items():
            doc_full_path = os.path.join(opf_dir, href)
            
            # Don't inject into our own footnote file
            if doc_full_path == footnote_full_path or not os.path.exists(doc_full_path):
                continue
                
            # Calculate relative path to footnotes file
            rel_footnote_path = os.path.relpath(footnote_full_path, os.path.dirname(doc_full_path))
            # Fix backslashes for EPUB hrefs
            rel_footnote_path = rel_footnote_path.replace('\\', '/')
                
            with open(doc_full_path, 'rb') as f:
                content = f.read()
                
            soup = BeautifulSoup(content, 'html.parser')
            modified = False
            
            html_tag = soup.find('html')
            if html_tag and not html_tag.has_attr('xmlns:epub'):
                html_tag['xmlns:epub'] = "http://www.idpf.org/2007/ops"
                modified = True
                
            body = soup.find('body')
            target_container = body if body else soup
            
            def dynamic_replace(match):
                matched_text = match.group(0)
                entity_key = matched_text.lower()
                safe_id = entity_key.replace(" ", "_").replace("'", "")
                return (
                    f'<a href="{rel_footnote_path}#{safe_id}" epub:type="noteref" '
                    f'style="color: inherit !important; text-decoration: none !important; border: none !important; white-space: nowrap !important;">'
                    f'{matched_text}'
                    f'</a>'
                )

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
                with open(doc_full_path, 'wb') as f:
                    f.write(str(soup).encode('utf-8'))
                    
        # 6. Re-zip the EPUB
        with zipfile.ZipFile(output_epub_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            # Add mimetype first (uncompressed)
            mimetype_path = os.path.join(temp_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                new_zip.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
                
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file == 'mimetype' and root == temp_dir:
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, arcname)

def process_sigil_and_inject(sigil_path: str, epub_path: str, output_epub_path: str):
    """
    Master function: Reads .sigil file and injects the extracted JSON data
    into the target EPUB as footnotes.
    """
    xray_list = unpack_sigil(sigil_path)
    inject_xray_footnotes(epub_path, xray_list, output_epub_path)
    return True
