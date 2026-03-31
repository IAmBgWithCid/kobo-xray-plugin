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

def ner_extraction(chapters: dict) -> dict:
    entity_map = {}
    
    for chapter_num, (filename, text) in enumerate(chapters.items(), start=1):
        doc = nlp(text)
        
        for ent in doc.ents:
            if ent.label_ not in LABEL_MAP:
                continue
            
            entity_key = ent.text.lower().strip()
            category = LABEL_MAP[ent.label_]

            if nlp.vocab[entity_key].is_stop:
                continue
            if len(entity_key) < 3:
                continue
            
            if entity_key not in entity_map:
                starting_line = text.rfind("\n", 0, ent.start_char)
                ending_line = text.find("\n", ent.end_char)   
                if starting_line == -1:
                    starting_line = 0
                if ending_line == -1:
                    ending_line = len(text)   
                entity_map[entity_key] = {
                    "type": category,
                    "first_occurrence": chapter_num,
                    "summary_history": [],
                    "aliases": [],
                    "context": text[starting_line:ending_line].strip()
                }
    
    return entity_map

def substring_relation(entity_map: dict) -> dict:
    for entity_key, data in entity_map.items():
        for other_key in entity_map.keys():
            if entity_key != other_key and entity_key in other_key:
                if other_key not in data["aliases"]:
                    data["aliases"].append(other_key)
                if entity_key not in entity_map[other_key]["aliases"]:
                    entity_map[other_key]["aliases"].append(entity_key)
    return entity_map

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
    

    for pair, count in co_occurrence_relations.items():
        if count > 1:  # Only keep pairs that co-occur more than once
            if pair[1] not in entity_map[pair[0]]["aliases"]:
                entity_map[pair[0]]["aliases"].append(pair[1])
            if pair[0] not in entity_map[pair[1]]["aliases"]:
                entity_map[pair[1]]["aliases"].append(pair[0])

    return entity_map
        
        

if __name__ == "__main__":
    path = "The Way of Kings_ The Stormlight Archive.epub"
    chapters = extract_chapters(path)
    entity_map = ner_extraction(chapters)
    entity_map = substring_relation(entity_map)
    entity_map = co_occurrence_relation(entity_map, chapters)

    for name, data in entity_map.items():
        print(f"{name} | {data['type']} | first seen: chapter {data['first_occurrence']} | aliases: {data['aliases']} | context: {data['context'][:50]}...\n")