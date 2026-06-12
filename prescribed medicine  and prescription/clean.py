import json
import re


def clean_text(text):
    """
    Cleans raw database text by removing HTML tags, scrubbing hidden line breaks,
    fixing duplicate white spaces, and ensuring normalized formatting.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Remove HTML/XML/SVG structural tags
    text = re.sub(r'<[^>]+?>', ' ', text)

    # 2. Strip URLs, image paths, file references, or base64 patterns
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'\b\S+\.(?:png|jpg|jpeg|gif|pdf|svg)\b', '', text, flags=re.IGNORECASE)

    # 3. Clean up formatting (replace carriage returns/newlines with spaces)
    text = text.replace('\r', ' ').replace('\n', ' ')

    # 4. Standardize space blocks (reduce duplicate spaces to a single clean space)
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def clean_row(row):
    """
    Cleans a single row.  A row can be:
      • a list  – original format used by prescription / prescribed_medicine
      • a dict  – new format used by treatment (keys: id, title, description, …)
    """
    if isinstance(row, dict):
        return {k: (clean_text(v) if isinstance(v, str) else v)
                for k, v in row.items()}

    # plain list
    cleaned = []
    for item in row:
        if isinstance(item, str):
            cleaned.append(clean_text(item))
        else:
            cleaned.append(item)
    return cleaned


def process_cleaning_pipeline(input_json_path, output_json_path):
    print(f"Loading raw extracted records from: {input_json_path}")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaned_data = {}

    for table_name, records in data.items():
        cleaned_data[table_name] = [clean_row(row) for row in records]

    with open(output_json_path, 'w', encoding='utf-8') as out:
        json.dump(cleaned_data, out, indent=4, ensure_ascii=False)

    print("🧼 Cleaning complete! All fields have been scrubbed.")
    print(f"Cleaned records saved to: {output_json_path}")


if __name__ == "__main__":
    input_file  = "/Users/mahadi/Desktop/fold/extracted_raw_data.json"
    output_file = "/Users/mahadi/Desktop/fold/cleaned_data.json"

    try:
        process_cleaning_pipeline(input_file, output_file)
        print("\n=== SUCCESS: DATA CLEANING COMPLETE ===")
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{input_file}'. Please run Step 3 first.")
