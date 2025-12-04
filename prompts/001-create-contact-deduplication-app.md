<objective>
Create a Python application for merging duplicate contacts from an iOS contacts export in vCard format. The application must handle 10,000+ contacts with many duplicates created during Android-to-iPhone migration, ensuring no information is lost during the merge process. The solution must include proper project structure, virtual environment setup, and provide both preview mode and detailed logging capabilities.
</objective>

<context>
This is a new Python project for contact deduplication. The user migrated from Android to iPhone, resulting in duplicate contacts that need to be intelligently merged while preserving all contact information. The application will process large vCard files (10,000+ contacts) and must be efficient and user-friendly.

Project requirements:
- New project setup with proper directory structure
- Python virtual environment configuration
- .gitignore file for Python projects
- Efficient processing of large contact datasets
- User-friendly preview and confirmation workflow
</context>

<requirements>

<functional_requirements>
1. **vCard Parsing**: Read and parse iOS vCard export files (.vcf format)
2. **Duplicate Detection**: Identify duplicates using a combination of methods:
   - Exact name matching (first name + last name)
   - Phone number matching (normalized for comparison)
   - Email address matching (case-insensitive)
   - Fuzzy name matching (handle typos, variations, nicknames)
3. **Intelligent Merging**: When duplicates are found, intelligently combine all fields:
   - Merge multiple phone numbers into a single contact
   - Merge multiple email addresses
   - Combine address fields intelligently
   - Preserve all custom fields, notes, photos, and metadata
   - Handle conflicting data by keeping all unique values
4. **Preview Mode**: Before final merge, display:
   - Summary of duplicates found
   - Preview of how contacts will be merged
   - Statistics (total contacts, duplicates found, contacts after merge)
5. **Detailed Logging**: Generate comprehensive logs showing:
   - Which contacts were identified as duplicates
   - Matching criteria used for each duplicate group
   - Fields merged for each contact
   - Any conflicts or edge cases handled
6. **Output**: Generate a new vCard file with deduplicated contacts
</functional_requirements>

<performance_requirements>
- Efficiently process 10,000+ contacts without excessive memory usage
- Provide progress indicators for long-running operations
- Optimize duplicate detection algorithms for large datasets
</performance_requirements>

<project_structure>
Create a proper Python project structure:
```
Contact_Deduplication/
├── .gitignore
├── README.md
├── requirements.txt
├── venv/ (virtual environment - create setup instructions)
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── vcard_parser.py
│   ├── duplicate_detector.py
│   ├── contact_merger.py
│   ├── preview_generator.py
│   └── logger.py
├── data/
│   ├── input/ (for input vCard files)
│   └── output/ (for merged vCard files)
├── logs/ (for detailed merge logs)
└── tests/ (optional test structure)
```
</project_structure>

</requirements>

<implementation>

<libraries_and_dependencies>
Use appropriate Python libraries:
- `vobject` or `vcard` library for vCard parsing
- `fuzzywuzzy` or `rapidfuzz` for fuzzy string matching
- `phonenumbers` library for phone number normalization
- Standard library: `logging`, `argparse`, `pathlib`, `json` (for preview data)

Include all dependencies in `requirements.txt` with version specifications.
</libraries_and_dependencies>

<duplicate_detection_algorithm>
Thoroughly analyze and implement a multi-stage duplicate detection approach:

1. **Normalization Phase**: Normalize all contact data for comparison:
   - Phone numbers: Remove formatting, handle country codes
   - Email addresses: Lowercase, trim whitespace
   - Names: Normalize whitespace, handle common variations

2. **Exact Matching**: First pass using exact matches on:
   - Normalized phone numbers
   - Normalized email addresses
   - Exact name matches (first + last)

3. **Fuzzy Matching**: Second pass using fuzzy matching for:
   - Similar names (handle typos, nicknames, middle name variations)
   - Consider contacts with matching phone OR email but different names
   - Use configurable similarity threshold (default: 85%)

4. **Grouping**: Group all identified duplicates together, handling cases where:
   - Contact A matches Contact B
   - Contact B matches Contact C
   - Therefore A, B, C should all be in the same group
</duplicate_detection_algorithm>

<intelligent_merging_strategy>
When merging duplicate contacts, implement intelligent field combination:

1. **Phone Numbers**: Merge all unique phone numbers, preserving labels (mobile, home, work, etc.)
2. **Email Addresses**: Merge all unique email addresses with their labels
3. **Addresses**: If multiple addresses exist, keep all unique addresses
4. **Names**: Use the most complete name (prefer longer/more detailed versions)
5. **Dates**: Keep all important dates (birthday, anniversary, etc.)
6. **Photos**: Prefer higher resolution or more recent photo
7. **Notes**: Combine notes intelligently, avoiding exact duplicates
8. **Custom Fields**: Preserve all custom fields and metadata
9. **Organization Info**: Merge company, title, department fields intelligently

For conflicting data (e.g., different birthdays), keep all values or use heuristics to determine the most likely correct value.
</intelligent_merging_strategy>

<preview_and_logging>
1. **Preview Generation**: Create a human-readable preview showing:
   - Duplicate groups with contact names
   - How each group will be merged
   - Field-by-field merge preview
   - Statistics dashboard

2. **Logging System**: Implement detailed logging to files:
   - Log file per run with timestamp
   - Log all duplicate detections with matching criteria
   - Log all merge operations with before/after states
   - Log any warnings or edge cases
   - Include summary statistics at the end

3. **User Interaction**: 
   - Display preview in terminal/console
   - Ask for user confirmation before final merge
   - Show progress during processing
   - Provide option to save preview to file
</preview_and_logging>

<code_quality>
- Write clean, well-documented Python code
- Include docstrings for all functions and classes
- Add type hints where appropriate
- Handle edge cases and errors gracefully
- Include input validation
- Make the code modular and maintainable
</code_quality>

</implementation>

<output>
Create the following files with relative paths:

1. `./.gitignore` - Python .gitignore with venv, __pycache__, .pyc files, IDE files, data files
2. `./README.md` - Comprehensive README with:
   - Project description
   - Installation instructions (including venv setup)
   - Usage examples
   - Requirements explanation
3. `./requirements.txt` - All Python dependencies with versions
4. `./src/__init__.py` - Package init file
5. `./src/main.py` - Main entry point with CLI argument parsing:
   - Input vCard file path
   - Output vCard file path
   - Preview mode flag
   - Logging level options
6. `./src/vcard_parser.py` - vCard file parsing module
7. `./src/duplicate_detector.py` - Duplicate detection logic with all matching strategies
8. `./src/contact_merger.py` - Intelligent contact merging logic
9. `./src/preview_generator.py` - Preview generation and display
10. `./src/logger.py` - Logging configuration and utilities
11. `./data/input/.gitkeep` - Placeholder for input directory
12. `./data/output/.gitkeep` - Placeholder for output directory
13. `./logs/.gitkeep` - Placeholder for logs directory

Create a virtual environment setup script or detailed instructions in README for:
- Creating venv: `python3 -m venv venv`
- Activating venv: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows)
- Installing dependencies: `pip install -r requirements.txt`
</output>

<verification>
Before declaring complete, verify:

1. **Project Structure**: All directories and files are created correctly
2. **Dependencies**: requirements.txt includes all necessary libraries with versions
3. **Code Completeness**: All modules implement their intended functionality
4. **Error Handling**: Code handles edge cases (empty files, malformed vCards, etc.)
5. **Documentation**: README provides clear setup and usage instructions
6. **Gitignore**: Properly excludes virtual environment and generated files
7. **Modularity**: Code is well-organized into logical modules
8. **Preview Mode**: Preview functionality displays merge information clearly
9. **Logging**: Logging system captures all necessary information

Test the structure by:
- Verifying all files exist in correct locations
- Checking that imports would work between modules
- Ensuring README instructions are clear and complete
</verification>

<success_criteria>
- Complete Python project structure with all necessary files
- Virtual environment setup instructions included
- vCard parsing functionality implemented
- Multi-strategy duplicate detection (exact + fuzzy matching)
- Intelligent contact merging preserving all fields
- Preview mode with user-friendly display
- Comprehensive logging system
- README with clear installation and usage instructions
- Code is production-ready, well-documented, and handles edge cases
- Application can process large vCard files (10,000+ contacts) efficiently
</success_criteria>

