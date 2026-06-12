import json
import re


def clean_text(text):
    """
    Cleans raw database text by removing HTML tags, URLs, file references,
    hidden line breaks, and duplicate spaces.
    """
    if not text or not isinstance(text, str):
        return ""

    text = re.sub(r'<[^>]+?>', ' ', text)
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'\b\S+\.(?:png|jpg|jpeg|gif|pdf|svg)\b', '', text, flags=re.IGNORECASE)
    text = text.replace('\r', ' ').replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def clean_value(value):
    """Recursively clean strings inside dict/list structures."""
    if isinstance(value, str):
        return clean_text(value)
    elif isinstance(value, dict):
        return clean_row(value)
    elif isinstance(value, list):
        return [clean_value(item) for item in value]
    return value


def clean_row(row):
    """
    Cleans a single row (dict or list).
    Removes: id, indexing
    Merges: description / description_web / description_api -> description
    """
    if isinstance(row, dict):
        cleaned = {}

        # Keep one description field only
        desc = ""
        for key in ["description", "description_web", "description_api"]:
            if key in row and row[key]:
                desc = clean_text(row[key]) if isinstance(row[key], str) else row[key]
                if desc:
                    break

        for k, v in row.items():
            if k in {"id", "indexing", "description", "description_web", "description_api"}:
                continue
            cleaned[k] = clean_value(v)

        if desc != "":
            cleaned["description"] = desc

        return cleaned

    # If row is a list, clean each item
    if isinstance(row, list):
        return [clean_value(item) for item in row]

    return row


def process_cleaning_pipeline(input_json_path, output_json_path):
    print(f"Loading raw extracted records from: {input_json_path}")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaned_data = {}

    for table_name, records in data.items():
        cleaned_data[table_name] = [clean_row(row) for row in records]

    with open(output_json_path, 'w', encoding='utf-8') as out:
        json.dump(cleaned_data, out, indent=4, ensure_ascii=False)

    print("🧼 Cleaning complete! Unwanted fields removed and text cleaned.")
    print(f"Cleaned records saved to: {output_json_path}")


if __name__ == "__main__":
    input_file = "/Users/mahadi/Desktop/html_free_treatment/extracted_raw_data.json"
    output_file = "/Users/mahadi/Desktop/html_free_treatment/cleaned_data.json"

    try:
        process_cleaning_pipeline(input_file, output_file)
        print("\n=== SUCCESS: DATA CLEANING COMPLETE ===")
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{input_file}'. Please run Step 3 first.")