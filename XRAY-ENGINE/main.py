import sys
import os
import time
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client

from ner import extract_from_epub
from summary import generate_all_summaries
from Injector import inject_xray_data


load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


NAMESPACE_SIGIL = uuid.uuid5(uuid.NAMESPACE_DNS, "sigil.community.project")

def run_pipeline(epub_path):
    print("========================================")
    print("STARTING IN-MEMORY X-RAY PIPELINE")
    print(f"Target: {epub_path}")
    print("========================================\n")
    start_time = time.time()

    base_path, ext = os.path.splitext(epub_path)
    
    book_title = os.path.basename(base_path).replace("_", " ").title()
    book_uuid = str(uuid.uuid5(NAMESPACE_SIGIL, book_title.lower().strip()))
    
    json_output_path = base_path + "_XRAY.json"
    final_epub_output = base_path + "_XRAY" + ext

    
    print("PHASE 1: NER Extraction")
    master_entity_map = extract_from_epub(epub_path)
    print("PHASE 1 COMPLETE!\n")

    # Free up GPU VRAM so Ollama can use it for Phase 2
    import ner
    if hasattr(ner, 'nlp'):
        del ner.nlp
    import gc
    import torch
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    
    print("PHASE 2: AI Summarization & Packing")
    sigil_file_path = generate_all_summaries(master_entity_map, output_filename=json_output_path)
    print("PHASE 2 COMPLETE!\n")

   
    print("PHASE 3: Local EPUB Link Injection")
    inject_xray_data(epub_path, json_output_path, final_epub_output)
    print("PHASE 3 COMPLETE!\n")

   
    print("PHASE 4: Uploading to The Archive...")
    try:
       
        supabase.table("works").upsert({
            "id": book_uuid,
            "primary_title": book_title
        }).execute()

        # 2. Upload the .sigil file to the secure vault
        with open(sigil_file_path, 'rb') as f:
            file_path_in_bucket = f"{book_uuid}.sigil"
            # Overwrite if a previous version exists
            supabase.storage.from_("sigil-vault").upload(
                file_path_in_bucket, f, {"upsert": "true"}
            )

        # 3. Log the manuscript (assuming plugin_device_id for now, you can hardcode a UUID for testing)
        supabase.table("decoded_manuscripts").insert({
            "work_id": book_uuid,
            "plugin_device_id": "local-test-device",
            "sigil_file_path": file_path_in_bucket
        }).execute()
        
        print("Upload successful!")
    except Exception as e:
        print(f"Error communicating with the Archive: {e}")

    # Finish
    end_time = time.time()
    elapsed_minutes = round((end_time - start_time) / 60, 2)
    print("========================================")
    print(f"PIPELINE FINISHED SUCCESSFULLY!")
    print(f"Total Time: {elapsed_minutes} minutes")
    print("========================================")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_book = sys.argv[1]
        run_pipeline(target_book)
    else:
        print("Error: No EPUB path provided. Please launch via Calibre.")