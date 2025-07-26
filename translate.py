import torch
import pysrt
import argparse
import os
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline

# --- Configuration ---
# A model specifically for translation.
MODEL_ID = "facebook/nllb-200-distilled-600M"

def setup_pipeline():
    """
    Sets up the translation pipeline with the specified NLLB model.
    This is the standard and most efficient way to use these models.
    """
    print(f"Loading model: {MODEL_ID}")
    print("This may take a few minutes depending on your connection speed...")

    # For NLLB, we use the high-level pipeline for simplicity and efficiency.
    # It handles batching, tokenization, and decoding automatically.
    # NLLB requires specific language codes.
    # src_lang = "eng_Latn" (English, Latin script)
    # tgt_lang = "tur_Latn" (Turkish, Latin script)
    translator = pipeline(
        "translation",
        model=MODEL_ID,
        tokenizer=MODEL_ID,
        src_lang="eng_Latn",
        tgt_lang="tur_Latn",
        device_map="auto" # Automatically use the GPU
    )
    
    print("Translation pipeline loaded successfully.")
    return translator

def translate_in_batches(translator, subs, batch_size=16):
    """
    Translates subtitles in batches for much greater speed.
    """
    # Extract just the text from the subtitle objects
    original_texts = [sub.text.replace('\n', ' ') for sub in subs]
    
    translated_texts = []
    
    # Use tqdm to show a progress bar over the batches
    print(f"\nTranslating in batches of {batch_size}...")
    for i in tqdm(range(0, len(original_texts), batch_size), desc="Translating Batches"):
        batch = original_texts[i:i+batch_size]
        
        # The pipeline handles the translation for the entire batch at once
        translated_batch = translator(batch)
        
        # Extract the translated text from the pipeline's output
        translated_texts.extend([item['translation_text'] for item in translated_batch])
        
    # Update the subtitle objects with the new translated text
    for i, sub in enumerate(subs):
        # Restore newlines if they were present in the original
        restored_text = translated_texts[i].replace(' ', '\n', sub.text.count('\n'))
        sub.text = restored_text

def main(input_file, output_file):
    """
    Main function to orchestrate the translation process.
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file not found at '{input_file}'")
        return

    # Load the specialized translation pipeline
    translator = setup_pipeline()

    # Load the SRT file
    print(f"\nLoading subtitle file: {input_file}")
    try:
        subs = pysrt.open(input_file, encoding='utf-8')
    except Exception as e:
        print(f"Error reading SRT file: {e}. Trying 'latin-1' encoding...")
        try:
            subs = pysrt.open(input_file, encoding='latin-1')
        except Exception as e_fallback:
            print(f"Fallback failed. Error: {e_fallback}")
            return
    
    print(f"Found {len(subs)} subtitle entries to translate.")

    # Translate all subtitles using the efficient batching function
    try:
        translate_in_batches(translator, subs)
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Saving partial progress...")
    finally:
        # Save the translated subtitles
        print(f"\nSaving translated subtitles to: {output_file}")
        subs.save(output_file, encoding='utf-8')
        print("Translation complete. File saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate an English SRT file to Turkish using an NLLB model.")
    parser.add_argument("input_file", help="The path to the input English SRT file.")
    parser.add_argument("output_file", help="The path where the translated Turkish SRT file will be saved.")
    
    args = parser.parse_args()
    
    main(args.input_file, args.output_file)
