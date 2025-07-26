import torch
import pysrt
import argparse
import os
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

# --- Configuration ---
MODEL_ID = "ByteDance-Seed/Seed-X-Instruct-7B"

def setup_model_and_tokenizer():
    """
    Sets up and loads the quantized model and tokenizer.
    """
    print(f"Loading model: {MODEL_ID}")
    print("This may take a few minutes depending on your connection speed...")

    # Configuration for 4-bit quantization
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    # Load the tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    
    # Load the model with quantization
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=quantization_config,
        torch_dtype=torch.bfloat16, # Use bfloat16 for computation
        device_map="auto",         # Automatically map model to available GPU
        trust_remote_code=True     # Required by this model
    )
    
    print("Model and tokenizer loaded successfully.")
    return model, tokenizer

def build_prompt(text):
    """
    Constructs the instruction prompt for the model.
    A good prompt is crucial for instruction-tuned models.
    """
    # This prompt structure clearly tells the model its role and task.
    prompt = (
        f"You are a professional subtitle translator. "
        f"Translate the following English text to Turkish. "
        f"Keep the meaning and tone the same. "
        f"Output ONLY the translated text, without any additional explanations, comments, or quotation marks.\n\n"
        f"English: \"{text}\"\n"
        f"Turkish:"
    )
    return prompt

def translate_text(model, tokenizer, text_to_translate):
    """
    Translates a single piece of text using the loaded model.
    """
    if not text_to_translate.strip():
        return "" # Return empty string if input is empty

    # Build the full prompt for the model
    prompt = build_prompt(text_to_translate)
    
    # Prepare model inputs
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    # Generate the translation
    # We set max_new_tokens to avoid overly long outputs. Adjust if needed.
    # The length of the input prompt is added to max_length to ensure enough space for the translation.
    output = model.generate(
        **inputs,
        max_new_tokens=len(text_to_translate.split()) * 3 + 20, # Heuristic for output length
        do_sample=False, # Use greedy decoding for more consistent translations
        pad_token_id=tokenizer.eos_token_id # Set pad token to end-of-sentence token
    )

    # Decode the output and clean it up
    full_output_text = tokenizer.decode(output[0], skip_special_tokens=True)
    
    # Isolate just the translated part by splitting after the prompt's end
    try:
        translated_text = full_output_text.split("Turkish:")[1].strip()
        # Remove potential quotation marks the model might add
        if translated_text.startswith('"') and translated_text.endswith('"'):
            translated_text = translated_text[1:-1]
        return translated_text
    except IndexError:
        # If the model output format is unexpected, return a placeholder
        print(f"\n[Warning] Could not parse model output: {full_output_text}")
        return "[Translation Error]"

def main(input_file, output_file):
    """
    Main function to orchestrate the translation process.
    """
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file not found at '{input_file}'")
        return

    # Load the model and tokenizer
    model, tokenizer = setup_model_and_tokenizer()

    # Load the SRT file using pysrt
    print(f"\nLoading subtitle file: {input_file}")
    try:
        subs = pysrt.open(input_file, encoding='utf-8')
    except Exception as e:
        print(f"Error reading SRT file: {e}")
        print("Trying with 'latin-1' encoding as a fallback...")
        try:
            subs = pysrt.open(input_file, encoding='latin-1')
        except Exception as e_fallback:
            print(f"Fallback failed. Error: {e_fallback}")
            return
    
    print(f"Found {len(subs)} subtitle entries to translate.")

    # Main translation loop with a progress bar and safety save
    try:
        for i in tqdm(range(len(subs)), desc="Translating Subtitles"):
            original_text = subs[i].text
            
            # Replace common SRT formatting with spaces for better translation
            cleaned_text = original_text.replace('\n', ' ')
            
            # Translate the cleaned text
            translated_text = translate_text(model, tokenizer, cleaned_text)
            
            # Restore newlines if they were present in the original
            subs[i].text = translated_text.replace(' ', '\n', original_text.count('\n'))

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Saving partial progress...")
    finally:
        # Save the translated subtitles to the output file
        # Using utf-8 is essential for Turkish characters
        print(f"\nSaving translated subtitles to: {output_file}")
        subs.save(output_file, encoding='utf-8')
        print("Translation complete. File saved.")


if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Translate an English SRT subtitle file to Turkish using Seed-X-Instruct-7B.")
    parser.add_argument("input_file", help="The path to the input English SRT file.")
    parser.add_argument("output_file", help="The path where the translated Turkish SRT file will be saved.")
    
    args = parser.parse_args()
    
    main(args.input_file, args.output_file)
