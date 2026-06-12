import re
import json
import html

SQL_FILE_PATH = "/Users/mahadi/Desktop/html_free_treatment/source_sql.sql"
OUTPUT_JSON_PATH = "/Users/mahadi/Desktop/html_free_treatment/extracted_raw_data.json"

TABLE_SCHEMAS = {
    "treatment": [
        "id",
        "title",
        "description",
        "description_web",
        "description_api",
        "disease_id",
        "indexing",
    ],
    "diseases": [
        "id",
        "name",
        "image",
        "category_of_disease_id",
        "is_paid",
        "serial",
    ],
    "category_of_disease": [
        "id",
        "name",
        "serial",
        "image",
    ],
}


def parse_sql_value(token):
    token = token.strip()

    if token.upper() == "NULL":
        return None

    if token.startswith("'") and token.endswith("'") and len(token) >= 2:
        token = token[1:-1]

    token = (
        token.replace("\\\\", "\\")
             .replace("\\'", "'")
             .replace('\\"', '"')
             .replace("\\n", "\n")
             .replace("\\r", "\r")
             .replace("\\t", "\t")
    )

    token = html.unescape(token)

    if re.fullmatch(r"-?\d+", token):
        try:
            return int(token)
        except ValueError:
            pass

    if re.fullmatch(r"-?\d+\.\d+", token):
        try:
            return float(token)
        except ValueError:
            pass

    return token


def find_statement_end(content, start):
    """
    Find the semicolon that ends the INSERT statement.
    Ignores semicolons inside quoted strings.
    """
    in_string = False
    escape = False
    i = start

    while i < len(content):
        ch = content[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                if i + 1 < len(content) and content[i + 1] == "'":
                    i += 1
                else:
                    in_string = False
        else:
            if ch == "'":
                in_string = True
            elif ch == ";":
                return i + 1

        i += 1

    return -1


def extract_tuples(values_text):
    """
    Extract all top-level tuples from a VALUES block.
    """
    tuples = []
    in_string = False
    escape = False
    depth = 0
    start = None
    i = 0

    while i < len(values_text):
        ch = values_text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                if i + 1 < len(values_text) and values_text[i + 1] == "'":
                    i += 1
                else:
                    in_string = False
        else:
            if ch == "'":
                in_string = True
            elif ch == "(":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ")":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        tuples.append(values_text[start:i + 1])
                        start = None

        i += 1

    return tuples


def split_tuple_fields(tuple_text):
    """
    Split one SQL tuple into fields by commas outside quoted strings.
    """
    s = tuple_text.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]

    fields = []
    current = []
    in_string = False
    escape = False
    i = 0

    while i < len(s):
        ch = s[i]

        if in_string:
            if escape:
                if ch == "n":
                    current.append("\n")
                elif ch == "r":
                    current.append("\r")
                elif ch == "t":
                    current.append("\t")
                else:
                    current.append(ch)
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    current.append("'")
                    i += 1
                else:
                    in_string = False
            else:
                current.append(ch)
        else:
            if ch == "'":
                in_string = True
            elif ch == ",":
                fields.append("".join(current).strip())
                current = []
            else:
                current.append(ch)

        i += 1

    fields.append("".join(current).strip())
    return fields


def extract_table_rows(content, table_name, expected_columns):
    insert_re = re.compile(
        rf"INSERT INTO\s+`{re.escape(table_name)}`\s*\((.*?)\)\s*VALUES\s*",
        re.IGNORECASE | re.DOTALL
    )

    rows = []
    matches = list(insert_re.finditer(content))
    print(f"Found {len(matches)} INSERT block(s) for {table_name}.")

    for block_no, m in enumerate(matches, start=1):
        columns_raw = m.group(1)
        columns = [c.strip(" `") for c in columns_raw.split(",")]

        values_start = m.end()
        values_end = find_statement_end(content, values_start)

        if values_end == -1:
            print(f"Warning: could not find end of INSERT block #{block_no} for {table_name}")
            continue

        values_text = content[values_start:values_end - 1]
        tuple_texts = extract_tuples(values_text)

        block_count = 0

        for tuple_text in tuple_texts:
            fields_raw = split_tuple_fields(tuple_text)
            fields = [parse_sql_value(x) for x in fields_raw]

            if len(fields) != len(columns):
                continue

            record = dict(zip(columns, fields))

            # Keep only expected columns if provided
            if expected_columns:
                record = {k: record.get(k) for k in expected_columns}

            rows.append(record)
            block_count += 1

        print(f"  Block #{block_no}: {block_count} row(s)")

    return rows


def parse_mysql_dump(sql_file_path):
    print(f"Reading: {sql_file_path}")

    with open(sql_file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    data = {}
    for table_name, expected_columns in TABLE_SCHEMAS.items():
        data[table_name] = extract_table_rows(content, table_name, expected_columns)

    return data


if __name__ == "__main__":
    try:
        data = parse_mysql_dump(SQL_FILE_PATH)

        total_rows = sum(len(rows) for rows in data.values())
        print("\n=== EXTRACTION SUMMARY ===")
        for table_name, rows in data.items():
            print(f"{table_name}: {len(rows)} row(s)")
        print(f"Total rows extracted: {total_rows}")

        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=4, ensure_ascii=False)

        print(f"Saved to: {OUTPUT_JSON_PATH}")

    except FileNotFoundError:
        print(f"ERROR: Could not find '{SQL_FILE_PATH}'.")
