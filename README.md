# Contact Deduplication Tool

A Python application for merging duplicate contacts from iOS contacts export in vCard format. This tool intelligently identifies and merges duplicate contacts while preserving all contact information, making it perfect for cleaning up contacts after migrating from Android to iPhone.

## Features

- **Multi-Strategy Duplicate Detection**: Uses exact matching (name, phone, email) and fuzzy matching to identify duplicates
- **Intelligent Merging**: Combines all contact fields intelligently without losing any information
- **ICE Contact Protection**: Emergency contacts (ICE) are automatically excluded from merging as they are intentional duplicates
- **Base64 Data Preservation**: Preserves all Apple-specific metadata and Base64-encoded binary data (photos, X-AB* fields, etc.)
- **Robust Parsing**: Handles malformed vCard blocks with Base64 data gracefully, ensuring no contacts are lost
- **Enhanced Preview Mode**: Shows first 10 duplicate groups, with option to preview all merges before proceeding
- **Detailed Logging**: Comprehensive logs including name extraction fixes, duplicate detection, and merge operations
- **High Performance**: Efficiently handles 10,000+ contacts
- **User-Friendly**: Interactive CLI with progress indicators and confirmation prompts

## Requirements

- Python 3.8 or higher
- pip (Python package manager)

## Installation

### 1. Clone or Download this Repository

```bash
cd Contact_Deduplication
```

### 2. Create a Virtual Environment

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

1. Export your contacts from iOS as a vCard file (.vcf) and place it in the `data/input/` directory

2. Run the application:
```bash
python src/main.py --input data/input/contacts.vcf --output data/output/merged_contacts.vcf
```

### Command Line Options

```bash
python src/main.py [OPTIONS]

Required Options:
  --input, -i PATH          Path to input vCard file (.vcf)
  --output, -o PATH         Path to output vCard file (.vcf)

Optional Options:
  --preview, -p             Enable preview mode (default: True)
  --no-preview              Disable preview mode
  --no-validate             Skip output validation (not recommended)
  --log-level LEVEL         Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --fuzzy-threshold NUM     Fuzzy matching threshold 0-100 (default: 85)
  --no-confirm              Skip confirmation prompt (use with caution)
```

### Examples

**Preview mode with confirmation:**
```bash
python src/main.py -i data/input/contacts.vcf -o data/output/merged.vcf
```

**Disable preview mode:**
```bash
python src/main.py -i data/input/contacts.vcf -o data/output/merged.vcf --no-preview
```

**Skip preview and auto-confirm:**
```bash
python src/main.py -i data/input/contacts.vcf -o data/output/merged.vcf --no-preview --no-confirm
```

**Skip output validation (not recommended):**
```bash
python src/main.py -i data/input/contacts.vcf -o data/output/merged.vcf --no-validate
```

**Verbose logging:**
```bash
python src/main.py -i data/input/contacts.vcf -o data/output/merged.vcf --log-level DEBUG
```

## How It Works

### Duplicate Detection

The application uses a multi-stage approach to identify duplicates:

1. **Normalization**: Normalizes phone numbers, email addresses, and names for comparison
2. **Exact Matching**: Finds duplicates using:
   - Exact name matches (first + last name)
   - Matching phone numbers (normalized)
   - Matching email addresses (case-insensitive)
3. **Fuzzy Matching**: Uses fuzzy string matching to catch:
   - Similar names with typos or variations
   - Nicknames and alternate spellings
   - Contacts with matching phone/email but different names
4. **ICE Contact Exclusion**: Contacts with "ICE" in their name are automatically excluded from merging, as these are intentional emergency contacts

### Intelligent Merging

When duplicates are found, the tool intelligently combines:

- **Phone Numbers**: All unique phone numbers with their labels (mobile, home, work, etc.)
- **Email Addresses**: All unique email addresses with labels
- **Addresses**: All unique addresses preserved
- **Names**: Most complete name version preferred
- **Dates**: All important dates (birthday, anniversary)
- **Photos**: Higher resolution or more recent photo preferred
- **Notes**: Combined intelligently, avoiding duplicates
- **Custom Fields**: All custom fields and metadata preserved, including Apple-specific X-AB* fields
- **Organization**: Company, title, department merged intelligently
- **Base64 Data**: All Base64-encoded binary data (photos, Apple metadata) is preserved exactly as in the original

### Data Preservation

The tool ensures **zero data loss**:

- **Base64 Binary Data**: Apple's Base64-encoded binary data (photos, X-ABShowAs, itemX.* fields) is preserved exactly
- **Malformed Blocks**: Contacts with parsing issues are handled gracefully - raw vCard blocks are preserved and written back unchanged
- **Name Extraction**: If a contact name is missing or a placeholder, the tool:
  - Extracts name from FN field in raw vCard
  - Falls back to organization name if available
  - Logs all name corrections for review
- **Complete Contact Recovery**: All contacts from the export are processed, even those with Base64 data that causes parsing issues

### Preview and Logging

- **Preview Workflow**:
  1. Shows statistics and first 10 duplicate groups
  2. Displays first 10 merge previews
  3. Option to view all merge previews if there are more than 10
  4. Final confirmation prompt before proceeding
- **Logging**: Detailed logs saved to `logs/` directory with:
  - Name extraction fixes (when empty/placeholder names are corrected)
  - Duplicate detection results with matching criteria
  - Merge operations with before/after states
  - Warnings and edge cases
  - Summary statistics
  - ICE contact exclusions

## Project Structure

```
Contact_Deduplication/
├── .gitignore
├── README.md
├── requirements.txt
├── venv/                    # Virtual environment (create with python3 -m venv venv)
├── src/
│   ├── __init__.py
│   ├── main.py              # Main entry point
│   ├── vcard_parser.py      # vCard file parsing
│   ├── duplicate_detector.py # Duplicate detection logic
│   ├── contact_merger.py    # Contact merging logic
│   ├── preview_generator.py # Preview generation
│   └── logger.py            # Logging utilities
├── data/
│   ├── input/              # Place your .vcf files here
│   └── output/             # Merged contacts saved here
└── logs/                   # Detailed merge logs
```

## Troubleshooting

### "No module named 'vobject'"
Make sure you've activated the virtual environment and installed dependencies:
```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Malformed vCard Files
The tool handles malformed vCard files gracefully, including those with Base64-encoded binary data. If you see warnings about skipped blocks, those contacts are still preserved using manual parsing. All contacts from your export will be included in the output.

### Missing Contact Names
If contacts have empty or placeholder names, the tool will:
- Extract names from the vCard FN field
- Use organization name as fallback
- Assign a placeholder only if no other option exists
- Log all name corrections for your review

### ICE Contacts
Emergency contacts (ICE) are automatically detected and excluded from merging. They will appear in the output unchanged, preserving your emergency contact setup.

## License

This project is provided as-is for personal use.

## Contributing

This is a personal project, but suggestions and improvements are welcome!

