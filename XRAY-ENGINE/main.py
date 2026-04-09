import sys
import os
import time
from ner import extract_from_epub
from summary import generate_all_summaries
from Injector import inject_xray_data


def run_pipeline(epub_path):
    print("========================================")
    print("STARTING IN-MEMORY X-RAY PIPELINE")
    print(f"Target: {epub_path}")
    print("========================================\n")
    start_time = time.time()

    # Your fix: Absolute pathing derived directly from the target EPUB
    base_path, ext = os.path.splitext(epub_path)
    json_output_path = base_path + "_XRAY.json"
    final_epub_output = base_path + "_XRAY" + ext

    # Step 1: Run NER
    print("PHASE 1: NER Extraction")
    master_entity_map = extract_from_epub(epub_path)
    print("PHASE 1 COMPLETE!\n")

    # Step 2: Summarization
    print("PHASE 2: AI Summarization")
    generate_all_summaries(master_entity_map, output_filename=json_output_path)
    print("PHASE 2 COMPLETE!\n")

    # Step 3: Injection (Closing the loop for the Calibre UI)
    print("PHASE 3: EPUB Link Injection")
    inject_xray_data(epub_path, json_output_path, final_epub_output)
    print("PHASE 3 COMPLETE!\n")

    # Finish
    end_time = time.time()
    elapsed_minutes = round((end_time - start_time) / 60, 2)
    print("========================================")
    print(f"PIPELINE FINISHED SUCCESSFULLY!")
    print(f"Total Time: {elapsed_minutes} minutes")
    print("========================================")

if __name__ == "__main__":
    # Catch the file path sent by Calibre
    if len(sys.argv) > 1:
        target_book = sys.argv[1]
        run_pipeline(target_book)
    else:
        print("Error: No EPUB path provided. Please launch via Calibre.")