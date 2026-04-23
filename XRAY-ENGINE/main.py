import sys
import os
import time
import uuid
import argparse
import gc
from dotenv import load_dotenv

# --- 1. ROBUST ENVIRONMENT LOADING ---
def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

bundle_dir = get_bundle_dir()
exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else bundle_dir
cwd_dir = os.getcwd()

dotenv_candidates = [
    os.path.join(exe_dir, '.env'),
    os.path.join(bundle_dir, '.env'),
    os.path.join(cwd_dir, '.env')
]

loaded = False
for path in dotenv_candidates:
    if os.path.exists(path):
        print(f"DEBUG: Loading environment from: {path}")
        load_dotenv(path, override=True)
        loaded = True
        break

if not loaded:
    load_dotenv()

# Extract Variables
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
cuda = os.environ.get("CUDA_PATH")

# Setup CUDA PATH for CuPy/PyTorch compatibility
if cuda:
    print(f"DEBUG: Setting CUDA_PATH: {cuda}")
    bin_path = os.path.join(cuda, "bin")
    if os.path.exists(bin_path):
        os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")

if not url or not key:
    print("CRITICAL ERROR: SUPABASE_URL or SUPABASE_KEY missing from environment!")
    print(f"Searched paths: {dotenv_candidates}")
    sys.exit(1)

# --- 2. LATE IMPORTS (Ensures env vars are ready) ---
from supabase import create_client, Client
supabase: Client = create_client(url, key)

import ner
from summary import generate_all_summaries
from Injector import inject_xray_data

NAMESPACE_SIGIL = uuid.uuid5(uuid.NAMESPACE_DNS, "sigil.community.project")

def run_pipeline(epub_path, model_name="llama3", manual_title=None):
    print("========================================")
    print("STARTING IN-MEMORY X-RAY PIPELINE")
    print(f"Target: {epub_path}")
    print("========================================\n")
    start_time = time.time()

    base_path, ext = os.path.splitext(epub_path)
    
    if manual_title:
        book_title = manual_title
    else:
        book_title = os.path.basename(base_path).replace("_", " ").title()
        
    book_uuid = str(uuid.uuid5(NAMESPACE_SIGIL, book_title.lower().strip()))
    
    json_output_path = base_path + "_XRAY.json"
    final_epub_output = base_path + "_XRAY" + ext

    # PHASE 1: NER Extraction
    print("PHASE 1: NER Extraction")
    master_entity_map = ner.extract_from_epub(epub_path)
    print("PHASE 1 COMPLETE!\n")

    # --- GPU OPTIMIZATION: Clear VRAM for Ollama ---
    print("DEBUG: Clearing GPU VRAM for Ollama Phase...")
    if hasattr(ner, 'nlp'):
        del ner.nlp
    
    import torch
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # PHASE 2: AI Summarization
    print("PHASE 2: AI Summarization & Packing")
    sigil_file_path = generate_all_summaries(master_entity_map, output_filename=json_output_path, model_name=model_name)
    print("PHASE 2 COMPLETE!\n")

    # PHASE 3: Injection
    print("PHASE 3: Local EPUB Link Injection")
    inject_xray_data(epub_path, json_output_path, final_epub_output)
    print("PHASE 3 COMPLETE!\n")

    # PHASE 4: Upload
    print("PHASE 4: Uploading to The Archive...")
    try:
        supabase.table("works").upsert({
            "id": book_uuid,
            "primary_title": book_title
        }).execute()

        with open(sigil_file_path, 'rb') as f:
            file_path_in_bucket = f"{book_uuid}.sigil"
            supabase.storage.from_("sigil-vault").upload(
                file_path_in_bucket, f, {"upsert": "true"}
            )

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
    parser = argparse.ArgumentParser(description="Kobo X-Ray Engine")
    parser.add_argument("epub_path", help="Path to the EPUB file")
    parser.add_argument("--model", type=str, default="llama3", help="Ollama model to use")
    parser.add_argument("--title", type=str, help="Optional title of the book")
    
    args = parser.parse_args()
    
    if os.path.exists(args.epub_path):
        run_pipeline(args.epub_path, args.model, args.title)
    else:
        print(f"Error: EPUB file not found at {args.epub_path}")