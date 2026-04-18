import string
import nltk

import thinc.util
import torch
from thinc.util import assert_pytorch_installed, get_torch_default_device

# Patch thinc's xp2torch to fix cupy/torch dlpack incompatibility
# Must be done BEFORE spacy is imported!
_original_xp2torch = thinc.util.xp2torch
def patched_xp2torch(xp_tensor, requires_grad=False, device=None):
    assert_pytorch_installed()
    if device is None:
        device = get_torch_default_device()
    if hasattr(xp_tensor, "__dlpack__"):
        torch_tensor = torch.utils.dlpack.from_dlpack(xp_tensor)
    elif hasattr(xp_tensor, "toDlpack"):
        dlpack_tensor = xp_tensor.toDlpack()
        torch_tensor = torch.utils.dlpack.from_dlpack(dlpack_tensor)
    else:
        torch_tensor = torch.from_numpy(xp_tensor)
    torch_tensor = torch_tensor.to(device)
    if requires_grad:
        torch_tensor.requires_grad_()
    return torch_tensor
thinc.util.xp2torch = patched_xp2torch

import spacy
from Extractor import extract_chapters

is_using_gpu = spacy.prefer_gpu()
if is_using_gpu:
    print("Using GPU!")
    import thinc.api
    thinc.api.use_pytorch_for_gpu_memory()
else:
    print("Using CPU!")
nlp = spacy.load("en_core_web_trf")

nltk.download('words', quiet=True)
from nltk.corpus import words as nltk_words
ENGLISH_WORDS = set(w.lower() for w in nltk_words.words())


LABEL_MAP = {
    "PERSON": "character",
    "GPE": "location",
    "LOC": "location",
    "FAC": "location",
    "PRODUCT": "item",
    "ORG": "faction",
}

def ner_extraction(chapters: dict) -> dict:
    entity_map = {}
    
    # 2. Break chapters into smaller chunks (paragraphs) to prevent CUDA OOM errors
    chunked_data = []
    for chapter_num, (filename, text) in enumerate(chapters.items(), start=1):
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 10]
        for para in paragraphs:
            chunked_data.append((chapter_num, para))
            
    
    texts_only = [chunk[1] for chunk in chunked_data]
    
    
    for (chapter_num, original_text), doc in zip(chunked_data, nlp.pipe(texts_only, batch_size=256)):
        for ent in doc.ents:
            if ent.label_ not in LABEL_MAP:
                continue
            
            entity_key = ent.text.lower().replace('\u2019', "'").strip(string.punctuation)
            words = entity_key.split()
            
            while words and words[0] in nlp.Defaults.stop_words:
                words.pop(0)
            while words and words[-1] in nlp.Defaults.stop_words:
                words.pop()
            
            if not words:
                continue
                
            entity_key = " ".join(words)
            category = LABEL_MAP[ent.label_]
            
            if entity_key.endswith("'s"):
                entity_key = entity_key[:-2]
            
            if "\n" in entity_key or "?" in entity_key:
                continue
            if nlp.vocab[entity_key].is_stop or len(entity_key) < 3:
                continue
            if " " not in entity_key and entity_key in ENGLISH_WORDS:
                continue
            
            
            if entity_key not in entity_map:
                entity_map[entity_key] = {
                    "type": category,
                    "first_occurrence": chapter_num,
                    "summary_history": [],
                    "aliases": [],
                    "frequency": 1,
                    "context": [original_text]
                }
            else:
                if len(entity_map[entity_key]["context"]) < 3:
                    if original_text not in entity_map[entity_key]["context"]:
                        entity_map[entity_key]["context"].append(original_text)
                entity_map[entity_key]["frequency"] += 1
                
    return entity_map

#find substring relations between entities and add them as aliases
def substring_relation(entity_map: dict) -> dict:
    for entity_key, data in entity_map.items():
        for other_key in entity_map.keys():
            if entity_key != other_key and entity_key in other_key:
                if other_key not in data["aliases"]:
                    data["aliases"].append(other_key)
                if entity_key not in entity_map[other_key]["aliases"]:
                    entity_map[other_key]["aliases"].append(entity_key)
    return entity_map

#find co-occurrence relations between entities and add them as aliases if they co-occur more than once in the same paragraph
def co_occurrence_relation(entity_map: dict, chapters: dict) -> dict:
    co_occurrence_relations = {}
    for chapter_num, (filename, text) in enumerate(chapters.items(), start=1):
        doc = text.split("\n")
        for paragraph in doc:
            for entity_key in entity_map.keys():
                if entity_key in paragraph.lower():
                    for other_key in entity_map.keys():
                        if other_key != entity_key and other_key in paragraph.lower():
                            pair = tuple(sorted([entity_key, other_key]))
                            co_occurrence_relations[pair] = co_occurrence_relations.get(pair, 0) + 1
    
    #only keep pairs that co-occur more than once and add them as aliases to each other
    for pair, count in co_occurrence_relations.items():
        if count > 1:  # Only keep pairs that co-occur more than once
            if pair[1] not in entity_map[pair[0]]["aliases"]:
                entity_map[pair[0]]["aliases"].append(pair[1])
            if pair[0] not in entity_map[pair[1]]["aliases"]:
                entity_map[pair[1]]["aliases"].append(pair[0])

    return entity_map
        
        

def extract_from_epub(epub_path: str) -> dict:
    print(f" Extracting chapters from {epub_path}...")
    chapters = extract_chapters(epub_path)
    print(" Running NLP Entity Extraction...")
    entity_map = ner_extraction(chapters)
    print(" Mapping Substring Relations...")
    entity_map = substring_relation(entity_map)
    print(" Mapping Co-occurrence Relations...")
    entity_map = co_occurrence_relation(entity_map, chapters)
    return entity_map