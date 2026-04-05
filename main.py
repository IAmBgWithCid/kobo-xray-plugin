import time
from ner import extract_from_epub
from summary import generate_all_summaries

def run_pipeline():
    print("========================================")
    print("STARTING IN-MEMORY X-RAY PIPELINE")
    print("========================================\n")
    start_time = time.time()

    # Define your book
    epub_path = "The Way of Kings_ The Stormlight Archive.epub"
    output_path = "The_Way_of_Kings_XRAY_Final.json"

    # Step 1: Run NER and hold the dictionary in memory
    print("PHASE 1: NER Extraction")
    master_entity_map = extract_from_epub(epub_path)
    print("PHASE 1 COMPLETE!\n")

    # Step 2: Pass that memory directly to Ollama
    print("PHASE 2: AI Summarization")
    generate_all_summaries(master_entity_map, output_filename=output_path)
    print("PHASE 2 COMPLETE!\n")

    # Finish
    end_time = time.time()
    elapsed_minutes = round((end_time - start_time) / 60, 2)
    print("========================================")
    print(f"PIPELINE FINISHED SUCCESSFULLY!")
    print(f"Total Time: {elapsed_minutes} minutes")
    print("========================================")

if __name__ == "__main__":
    run_pipeline()