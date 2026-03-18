import spacy
from Extractor import extract_chapters

nlp = spacy.load("en_core_web_trf")

LABEL_MAP = {
    "PERSON": "character",
    "GPE": "location",
    "LOC": "location",
    "FAC": "location",
    "PRODUCT": "item",
    "ORG": "faction",
}

def build_entity_map(chapters: dict) -> dict:
    entity_map = {}
    
    for chapter_num, (filename, text) in enumerate(chapters.items(), start=1):
        doc = nlp(text)
        
        for ent in doc.ents:
            if ent.label_ not in LABEL_MAP:
                continue
            
            entity_key = ent.text.lower().strip()
            category = LABEL_MAP[ent.label_]
            
            if entity_key not in entity_map:
                entity_map[entity_key] = {
                    "type": category,
                    "first_occurrence": chapter_num,
                    "summary_history": []
                }
    
    return entity_map

if __name__ == "__main__":
    path = "The Way of Kings_ The Stormlight Archive.epub"
    chapters = extract_chapters(path)
    entity_map = build_entity_map(chapters)
    
    for name, data in entity_map.items():
        print(f"{name} | {data['type']} | first seen: chapter {data['first_occurrence']}")