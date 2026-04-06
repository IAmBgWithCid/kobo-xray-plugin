import string
import nltk
import spacy
from Extractor import extract_chapters
nltk.download('words')
from nltk.corpus import words as nltk_words
ENGLISH_WORDS = set(w.lower() for w in nltk_words.words())
import json

nlp = spacy.load("en_core_web_trf")
#labels to extract: PERSON, GPE, LOC, FAC, PRODUCT, ORG
LABEL_MAP = {
    "PERSON": "character",
    "GPE": "location",
    "LOC": "location",
    "FAC": "location",
    "PRODUCT": "item",
    "ORG": "faction",
}
#extract entities, filter by label, and store in a map with type, first occurrence, summary history, aliases, and context
def ner_extraction(chapters: dict) -> dict:
    entity_map = {}
    
    for chapter_num, (filename, text) in enumerate(chapters.items(), start=1):
        doc = nlp(text)
        
        for ent in doc.ents:
            if ent.label_ not in LABEL_MAP:
                continue
            
            entity_key = ent.text.lower().replace('\u2019', "'").strip(string.punctuation)
            words = entity_key.split()
            while words and words[0] in nlp.Defaults.stop_words:
                words.pop(0)
            while words and words[-1] in nlp.Defaults.stop_words:
                words.pop()
            entity_key = " ".join(words)
            category = LABEL_MAP[ent.label_]
            if entity_key.endswith("'s"):
                entity_key = entity_key[:-2]
            
            if "\n" in entity_key:
                continue
            if "?" in entity_key:
                continue
            #filter out stop words and short entities
            if nlp.vocab[entity_key].is_stop:
                continue
            if len(entity_key) < 3:
                continue
            if " " not in entity_key and entity_key in ENGLISH_WORDS:
                continue
            #only add the entity if it hasn't been seen before, and store the context of the first occurrence
            if entity_key not in entity_map:
                #find the line of the first occurrence and store the surrounding text as context
                starting_line = text.rfind("\n\n", 0, ent.start_char)
                ending_line = text.find("\n\n", ent.end_char)  
                if starting_line == -1:
                    starting_line = 0
                if ending_line == -1:
                    ending_line = len(text)   
                entity_map[entity_key] = {
                    "type": category,
                    "first_occurrence": chapter_num,
                    "summary_history": [],
                    "aliases": [],
                    "frequency": 1,
                    #store the context of the first occurrence, which is the surrounding text of the entity
                    "context": [text[starting_line:ending_line].strip()]
                }
            else:
                if len(entity_map[entity_key]["context"]) < 3:  # Only store context for the first few occurrences to save memory
                    starting_line = text.rfind("\n\n", 0, ent.start_char)
                    ending_line = text.find("\n\n", ent.end_char)  
                    if starting_line == -1:
                        starting_line = 0
                    if ending_line == -1:
                        ending_line = len(text)  
                    new_context = text[starting_line:ending_line].strip() 
                    if new_context not in entity_map[entity_key]["context"]:
                        entity_map[entity_key]["context"].append(new_context)

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
    print(f"📖 Extracting chapters from {epub_path}...")
    chapters = extract_chapters(epub_path)
    print("🧠 Running NLP Entity Extraction...")
    entity_map = ner_extraction(chapters)
    print("🔗 Mapping Substring Relations...")
    entity_map = substring_relation(entity_map)
    print("🔗 Mapping Co-occurrence Relations...")
    entity_map = co_occurrence_relation(entity_map, chapters)
    return entity_map