import json
import ollama
import zlib      
import hashlib   
import struct
import time

def build_prompt(name, entity, entity_map): 
    # Safely get the top aliases
    top_aliases = sorted(
        entity.get("aliases", []),
        key=lambda alias: entity_map[alias]["frequency"] if alias in entity_map else 0,
        reverse=True
    )[:3] 
    
    # 1. Provide the raw data clearly
    prompt = f"### ENTITY DATA\n"
    prompt += f"- Target Entity: {name}\n"
    prompt += f"- NER Suggested Type: {entity.get('type', 'UNKNOWN')} (WARNING: NER may be incorrect)\n"
    prompt += f"- Frequency Count: {entity.get('frequency', 0)}\n\n"
    
    # 2. Provide the Main Context safely
    # If context is a list of paragraphs, join them nicely. If it's a string, just print it.
    context_data = entity.get('context', '')
    if isinstance(context_data, list):
        context_data = "\n".join(context_data)
    prompt += f"### MAIN CONTEXT\n{context_data}\n\n"
    
    # 3. Provide Alias Contexts
    if top_aliases:
        prompt += f"### POTENTIAL ALIAS CONTEXTS\n"
        for alias in top_aliases:
            if alias in entity_map and "context" in entity_map[alias] and len(entity_map[alias]["context"]) > 0:
                alias_context = entity_map[alias]["context"][0]
                prompt += f"Alias '{alias}': {alias_context}\n"
        prompt += "\n"
    
    # 4. Strict, Bulleted Instructions
    prompt += "### INSTRUCTIONS\n"
    prompt += "1. IDENTIFY THE TRUE NATURE: Read the context to determine if the Target Entity is a Person, Place, Faction, or Object. Ignore the 'NER Suggested Type' if the context proves it wrong.\n"
    prompt += "2. VERIFY ALIASES: The listed aliases were grouped by a flawed AI. They might actually be enemies or completely different people in the same room. ONLY treat an alias as the same entity if the text explicitly proves it (e.g., 'Kaladin, also known as Kal').\n"
    
    if entity.get("frequency", 0) >= 50:
        prompt += "3. GENERATE SUMMARY: Write a professional 2-3 sentence Kindle X-Ray summary. Focus on who or what the entity is, their role, and confirmed relations.\n"
    else:
        prompt += "3. GENERATE SUMMARY: Write a brief 1-2 sentence Kindle X-Ray summary. Focus strictly on defining what the entity is.\n"
        
    # The new, aggressive "Amnesia" constraint
    prompt += "4. CRITICAL ANTI-SPOILER RULE: You suffer from total amnesia regarding the wider 'Stormlight Archive' universe. You MUST ONLY use the words and events explicitly written in the MAIN CONTEXT above. Do NOT use your pre-trained knowledge. If a term, event, or magic system is not in the provided text, DO NOT include it in the summary under any circumstances.\n"
    prompt += "5. OUTPUT FORMAT: Return ONLY a raw JSON object with no explanation, no markdown formatting, and no code blocks. The keys must be exactly 'entity' and 'summary' , The value for the 'entity' key MUST be the exact Target Entity name provided at the top of this prompt. Do not replace it with a category.\n"
    
    return prompt

def generate_summary(name, entity, entity_map, model_name="llama3"):
    prompt = build_prompt(name, entity, entity_map)
    
    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert literary archivist creating Kindle X-Ray summaries for a fantasy novel. Your primary job is to correct flawed automated data, deduce the true identity of characters or objects from raw text, and output strict, perfectly formatted JSON."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            format="json", # Forces strictly valid JSON parsing
            think=False,
            options={
                "temperature": 0.1, # Low temperature keeps the model logical and prevents creative hallucinations
                "num_ctx": 2048,    # Reduce context window to save VRAM so it fits on the GPU
                "num_predict": 150  # We only need a short summary, this saves VRAM allocation
            }
        )

        result = json.loads(response["message"]["content"])
        return result
    except Exception as e:
        # Failsafe so your entire loop doesn't crash if the model glitches
        print(f"Error processing {name}: {e}")
        return {"entity": name, "summary": "Error generating summary."}

def pack_to_sigil(final_xray_data, output_path):
    print(f"\nSealing data into {output_path}...")
    
    # 1. Serialize and Compress
    json_bytes = json.dumps(final_xray_data).encode('utf-8')
    compressed_payload = zlib.compress(json_bytes)
    
    # 2. Create Checksum (Integrity)
    checksum = hashlib.sha256(compressed_payload).digest()
    
    # 3. Build .sigil File: [Magic(4)][Version(1)][Checksum(32)][Payload]
    with open(output_path, "wb") as f:
        f.write(b"SIGL")             # Magic Number
        f.write(struct.pack("B", 1)) # Version 1
        f.write(checksum)            # 32-byte SHA-256
        f.write(compressed_payload)
    print("Seal Complete. File is ready for the Archive.")

 
def generate_all_summaries(entity_map: dict, output_filename="XRAY_Final.json", model_name="llama3"):
    final_xray_data = []
    total_entities = len(entity_map)
    start_time = time.time()

    print(f"\n[INCANTATION START]: Transmuting {total_entities} entities...")

    for i, (name, entity) in enumerate(entity_map.items(), 1):
        # Calculate timing
        elapsed = time.time() - start_time
        avg_time_per_entity = elapsed / i
        remaining_entities = total_entities - i
        est_remaining_seconds = avg_time_per_entity * remaining_entities
        
        # Format for display: MM:SS
        est_min, est_sec = divmod(int(est_remaining_seconds), 60)
        
        # CRYPTIC PROGRESS: Shows number, not name.
        print(f"\rDecoding Entity {i}/{total_entities} | Est. Time Remaining: {est_min:02d}:{est_sec:02d} ", end="", flush=True)
        
        # Still pass the name to the AI, just don't print it!
        result = generate_summary(name, entity, entity_map, model_name)
        final_xray_data.append(result)

    # Save the raw JSON (for local Calibre injection)
    with open(output_filename, "w", encoding="utf-8") as outfile:
        json.dump(final_xray_data, outfile, indent=4, ensure_ascii=False)
        
    # Create the secure .sigil version for the server
    sigil_output_path = output_filename.replace(".json", ".sigil")
    pack_to_sigil(final_xray_data, sigil_output_path)

    print(f"\n\nSuccess! Summaries saved to {output_filename} and packed into {sigil_output_path}")
    return sigil_output_path # We need to pass this to the upload script