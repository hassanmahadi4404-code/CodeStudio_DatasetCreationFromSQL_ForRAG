import json
import os
import re


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def unpack_nested_value(val):  # [[['Fever']]] -> 'Fever'
    """Recursively unwrap nested lists like [[[value]]] -> value."""
    while isinstance(val, list):
        if not val:
            return ""
        val = val[0]
    return "" if val is None else val


def clean_text(text):  # remove html signs
    """Remove HTML/XML tags and normalize whitespace."""
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_row(row):  # unpack whole row
    """Apply recursive unpacking to every cell in a list-style row."""
    return [unpack_nested_value(item) for item in row]


def safe_get(row, idx, default=""):  # যদি index না থাকে তাহলে crash না করে।
    """Safe access by index."""
    if 0 <= idx < len(row):
        return row[idx]
    return default


# ─────────────────────────────────────────────────────────────────────────────
# Lookup builders
# ─────────────────────────────────────────────────────────────────────────────

def build_user_lookup(raw_users):
    """
    Build lookup:
      user_id -> {name: ...}
    """
    lookup = {}

    for row in raw_users:
        clean_row = normalize_row(row)

        # index 1 = user_id, index 2 = user name
        user_id = str(safe_get(clean_row, 1, "")).strip()
        name = clean_text(safe_get(clean_row, 2, ""))

        if user_id:
            lookup[user_id] = {"name": name}

    return lookup


def build_medicine_lookup(raw_medicines):
    """
    Build lookup:
      prescription_id -> list of medicine strings

    Expected legacy row layout:
      [id, prescription_id, ..., medicine_name, dosage, ..., duration]
    """
    lookup = {}

    for record in raw_medicines:
        if isinstance(record, dict):
            prescription_id = str(record.get("prescription_id", "")).strip()
            med_name = clean_text(record.get("medicine_name", ""))
            dosage = clean_text(record.get("dosage", ""))
            duration = clean_text(record.get("duration", ""))
        elif isinstance(record, list):
            row = normalize_row(record)

            # index 1 = prescription_id
            # index 3 = medicine name
            # index 4 = dosage
            # index 6 = duration
            prescription_id = str(safe_get(row, 1, "")).strip()
            med_name = clean_text(safe_get(row, 3, ""))
            dosage = clean_text(safe_get(row, 4, ""))
            duration = clean_text(safe_get(row, 6, ""))
        else:
            continue

        # condition removed as requested:
        # if not prescription_id or not med_name:
        #     continue

        extra = " - ".join([x for x in [dosage, duration] if x])
        med_detail = f"{med_name} ({extra})" if extra else med_name
        lookup.setdefault(prescription_id, []).append(med_detail)

    return lookup


def build_treatment_lookup(raw_treatments):
    """
    Build lookup:
    disease_id -> list of treatment dicts

    Expected list layout:
    [id, title, description, description_web, description_api, disease_id, indexing]

    Also supports dict records with keys:
    title, description, description_web, description_api, disease_id
    """
    lookup = {}

    for record in raw_treatments:
        if isinstance(record, dict):
            disease_id = str(record.get("disease_id", "")).strip()
            title = clean_text(record.get("title", ""))
            description = clean_text(record.get("description", ""))
            description_web = clean_text(record.get("description_web", ""))
            description_api = clean_text(record.get("description_api", ""))

        elif isinstance(record, list):
            row = normalize_row(record)

            # Based on legacy schema:
            # 0=id, 1=title, 2=description, 3=description_web,
            # 4=description_api, 5=disease_id, 6=indexing
            title = clean_text(safe_get(row, 1, ""))
            description = clean_text(safe_get(row, 2, ""))
            description_web = clean_text(safe_get(row, 3, ""))
            description_api = clean_text(safe_get(row, 4, ""))
            disease_id = str(safe_get(row, 5, "")).strip()
        else:
            continue

        if not disease_id:
            continue

        entry = {
            "title": title,
            "description": description,
            "description_web": description_web,
            "description_api": description_api,
        }

        lookup.setdefault(disease_id, []).append(entry)

    return lookup


# ─────────────────────────────────────────────────────────────────────────────
# Main export
# ─────────────────────────────────────────────────────────────────────────────

def generate_patient_dataset(cleaned_json_path, output_jsonl_path):
    print("🚀 Initializing dataset generation...")

    if not os.path.exists(cleaned_json_path):
        print(f"❌ ERROR: Cannot find '{cleaned_json_path}'.")
        return

    with open(cleaned_json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # ── 1. Build user lookup ────────────────────────────────────────────────
    users_lookup = build_user_lookup(raw_data.get("user", []))
    print(f"✅ User lookup built: {len(users_lookup)} users")

    # ── 2. Build medicine lookup ───────────────────────────────────────────
    medicines_lookup = build_medicine_lookup(raw_data.get("prescribed_medicine", []))
    print(f"✅ Medicine lookup built: {len(medicines_lookup)} prescriptions with medicines")

    # ── 3. Prepare output folder ────────────────────────────────────────────
    out_dir = os.path.dirname(output_jsonl_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    total_records = 0
    discarded_records = 0
    missing_fields = 0

    print("🧩 Stitching prescription records and writing JSONL...")

    with open(output_jsonl_path, "w", encoding="utf-8") as out_file:
        for row in raw_data.get("prescription", []):
            clean_row = normalize_row(row)

            if len(clean_row) < 2:
                continue

            # ── Column mapping based on prescription schema ─────────────────
            # 0  -> id
            # 1  -> user_id
            # 11 -> cf
            # 12 -> oe
            # 13 -> inv
            # 14 -> dx
            # 15 -> patientName
            # 16 -> gender
            # 17 -> age
            # 18 -> date
            # 19 -> advice
            # 20 -> signature

            prescription_id = str(safe_get(clean_row, 0, "")).strip()
            user_id = str(safe_get(clean_row, 1, "")).strip()

            chief_complaint = clean_text(safe_get(clean_row, 11, ""))
            examination = clean_text(safe_get(clean_row, 12, ""))
            investigations = clean_text(safe_get(clean_row, 13, ""))
            diagnosis = clean_text(safe_get(clean_row, 14, ""))
            patient_name = clean_text(safe_get(clean_row, 15, ""))
            gender = str(safe_get(clean_row, 16, "")).strip().lower()
            age = str(safe_get(clean_row, 17, "")).strip()
            date = clean_text(safe_get(clean_row, 18, ""))
            advice = clean_text(safe_get(clean_row, 19, ""))
            signature = clean_text(safe_get(clean_row, 20, ""))

            symptoms_list = [
                s.strip()
                for s in chief_complaint.split(",")
                if s.strip()
            ] if chief_complaint else []

            user_info = users_lookup.get(user_id, {})
            user_name = user_info.get("name", "")

            prescribed_medicines = sorted(set(medicines_lookup.get(prescription_id, [])))

            target_record = {
                "gender": gender,
                "age": age,
                "symptoms": symptoms_list,
                "chief_complaint": chief_complaint,
                "examination": examination,
                "investigations": investigations,
                "diagnosis": diagnosis,
                "advice": advice,
                "prescribed_medicines": prescribed_medicines,
            }

            # Skip totally empty records
            if (
                not target_record["diagnosis"]
                and not target_record["symptoms"]
                and not target_record["prescribed_medicines"]
                and not target_record["chief_complaint"]
                and not target_record["examination"]
                and not target_record["investigations"]
                and not target_record["advice"]
            ):
                discarded_records += 1
                continue

            if not target_record["gender"] or not target_record["age"]:
                missing_fields += 1

            out_file.write(json.dumps(target_record, ensure_ascii=False) + "\n")
            total_records += 1

    print("\n=============================================")
    print("      ✨ DATASET GENERATION REPORT ✨        ")
    print("=============================================")
    print(f"Total Records Generated:     {total_records}")
    print(f"Total Records Discarded:     {discarded_records}")
    print(f"Records with Missing Fields: {missing_fields}")
    print(f"Target Output Path:          {output_jsonl_path}")
    print(f"File Exists:                 {os.path.exists(output_jsonl_path)}")
    if os.path.exists(output_jsonl_path):
        print(f"File Size:                   {os.path.getsize(output_jsonl_path)} bytes")
    print("=============================================")


if __name__ == "__main__":
    cleaned_data_file = "/Users/mahadi/Desktop/fold/cleaned_data.json"
    final_output_file = "/Users/mahadi/Desktop/fold/patient_records.json"

    generate_patient_dataset(cleaned_data_file, final_output_file)