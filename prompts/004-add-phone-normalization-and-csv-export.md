<objective>
Add two new features to the contact deduplication tool:
1. Phone number normalization to E.164 international format (e.g., +31 6 12345678) with optional command-line control
2. CSV export functionality for contacts

Phone normalization should be controllable via a command-line option (off by default). If the option is not specified, the tool should interactively prompt the user whether to enable normalization. The normalization should reformat phone numbers in both vCard and CSV outputs to standard E.164 format while preserving phone type information.

CSV export should provide an alternative output format that's easy to import into spreadsheets and other applications, containing all key contact information in a structured format.
</objective>

<context>
The contact deduplication tool currently processes contacts from vCard files, detects duplicates, merges them, and outputs a cleaned vCard file. The tool already uses the `phonenumbers` library for phone number normalization during duplicate detection (in `duplicate_detector.py`), but the original phone number formats are preserved in the output.

Users need:
1. **Phone Normalization**: The ability to standardize phone numbers to E.164 format in the output files. This should be optional because some users may want to preserve original formats. The normalization should be:
   - Controlled via `--normalize-phones` command-line flag (off by default)
   - If flag is not provided, prompt the user interactively: "Normalize phone numbers to E.164 format? (yes/no): "
   - Applied to both vCard and CSV outputs when enabled
   - Preserve phone type information (home, work, mobile, etc.)

2. **CSV Export**: Export contacts to CSV format for easy viewing and import into other applications. The CSV should include:
   - All key contact fields (name, phones, emails, addresses, organization, etc.)
   - One row per contact
   - Multiple phones/emails/addresses handled appropriately (multiple columns or semicolon-separated)
   - Proper CSV formatting (handle commas, quotes, newlines in data)

@src/main.py - Main entry point, CLI argument parsing, workflow orchestration
@src/vcard_parser.py - vCard parsing and writing, phone number handling
@src/duplicate_detector.py - Phone normalization logic (already uses phonenumbers library)
@src/contact_merger.py - Contact merging logic
@requirements.txt - Dependencies (phonenumbers already included)
</context>

<requirements>

<functional_requirements>

<phone_normalization>
1. **Command-Line Option**:
   - Add `--normalize-phones` flag (action='store_true', default=False)
   - Add `--no-normalize-phones` flag to explicitly disable (for non-interactive use)
   - When neither flag is provided, prompt user: "Normalize phone numbers to E.164 format? (yes/no): "
   - Skip prompt if `--no-confirm` flag is used (default to False in that case)

2. **Normalization Logic**:
   - Use existing `phonenumbers` library (already in requirements.txt)
   - Normalize phone numbers to E.164 format (e.g., +31612345678 or +31 6 12345678 for display)
   - Preserve phone type information (home, work, mobile, etc.)
   - Handle invalid/unparseable numbers gracefully (keep original format, log warning)
   - Apply normalization to phone numbers in:
     - vCard output (when writing contacts)
     - CSV output (when exporting)

3. **Implementation Points**:
   - Create a phone normalization utility function that can be reused
   - Normalize phones after merging but before writing output
   - Store normalized numbers in contact dictionaries
   - Ensure normalization doesn't break existing duplicate detection (which already normalizes for comparison)
</phone_normalization>

<csv_export>
1. **Command-Line Option**:
   - Add `--csv` or `--export-csv` option that takes a file path
   - Example: `--csv data/output/contacts.csv`
   - CSV export should be optional (only when flag is provided)

2. **CSV Format**:
   - Include these columns (at minimum):
     - Name (full name)
     - First Name
     - Last Name
     - Phone 1, Phone 2, Phone 3 (or Phone 1 Type, Phone 1 Number, etc.)
     - Email 1, Email 2, Email 3 (or Email 1 Type, Email 1 Address, etc.)
     - Organization
     - Title
     - Address (formatted or separate fields: Street, City, Region, Postal Code, Country)
     - Notes
     - Birthday
     - Anniversary
   - Handle multiple phones/emails/addresses appropriately:
     - Option A: Multiple columns (Phone 1, Phone 2, Phone 3, etc.)
     - Option B: Semicolon-separated in single column (Phone: "123;456;789")
     - Option C: Separate type and number columns (Phone 1 Type, Phone 1 Number, Phone 2 Type, Phone 2 Number, etc.)
   - Use proper CSV escaping (handle commas, quotes, newlines in data)
   - Include header row with column names

3. **Implementation**:
   - Create new module `src/csv_exporter.py` for CSV export logic
   - Export should work with the same contact list used for vCard output
   - Apply phone normalization if enabled
   - Handle edge cases (missing fields, special characters, etc.)
</csv_export>

</functional_requirements>

<implementation>

<phone_normalization_approach>
1. **Create Normalization Utility**:
   - Add function in `src/vcard_parser.py` or create `src/phone_normalizer.py`
   - Function signature: `normalize_phone_to_e164(phone_number: str, default_region: str = "US") -> Optional[str]`
   - Use `phonenumbers.parse()` and `phonenumbers.format_number()` with `PhoneNumberFormat.E164`
   - Return None for invalid numbers (caller should preserve original)
   - Handle various input formats gracefully

2. **Integration Points**:
   - In `main.py`: Add CLI arguments and user prompt logic
   - After merging contacts, before writing output, normalize phones if enabled
   - In `write_vcard_file()`: Use normalized numbers when writing TEL fields
   - In CSV export: Use normalized numbers when writing phone columns

3. **Preserve Types**:
   - Normalization should only change the number format, not the type
   - Phone dictionary structure: `{'number': normalized_number, 'type': original_type}`
   - Ensure types are preserved through normalization process
</phone_normalization_approach>

<csv_export_approach>
1. **CSV Structure Decision**:
   - Use multiple columns approach for phones/emails/addresses (Phone 1, Phone 2, etc.)
   - Include type information: "Phone 1 Type", "Phone 1 Number", "Phone 2 Type", "Phone 2 Number", etc.
   - This provides better structure for spreadsheet applications
   - Determine max columns needed (e.g., up to 5 phones, 5 emails, 3 addresses)

2. **CSV Module**:
   - Create `src/csv_exporter.py` with:
     - `export_contacts_to_csv(contacts: List[Dict], output_path: Path, normalize_phones: bool = False) -> None`
     - Use Python's `csv` module (standard library) for proper CSV formatting
     - Handle special characters, commas, quotes, newlines correctly
     - Format dates appropriately (birthday, anniversary)

3. **Integration**:
   - In `main.py`: Add `--csv` argument, call exporter after contacts are finalized
   - Apply phone normalization before CSV export if enabled
   - Export to same directory as vCard output by default (or user-specified path)
</csv_export_approach>

<code_quality>
- Follow existing code patterns and style
- Add comprehensive error handling for invalid phone numbers
- Log normalization statistics (how many phones normalized, how many failed)
- Handle edge cases gracefully (no phones, invalid formats, etc.)
- Maintain backward compatibility (normalization off by default)
- Add comments explaining E.164 format and normalization logic
- Use type hints for better code clarity
</code_quality>

</implementation>

<output>
Create/modify the following files:

1. `./src/main.py` - Add CLI options and integration:
   - Add `--normalize-phones` and `--no-normalize-phones` arguments
   - Add interactive prompt for phone normalization (if flag not provided)
   - Add `--csv` or `--export-csv` argument for CSV export path
   - Integrate phone normalization into workflow (after merging, before output)
   - Integrate CSV export into workflow (after contacts finalized)

2. `./src/vcard_parser.py` or new `./src/phone_normalizer.py` - Phone normalization:
   - Add `normalize_phone_to_e164()` function
   - Add `normalize_contact_phones()` function to normalize all phones in a contact
   - Handle errors gracefully, preserve original if normalization fails

3. `./src/csv_exporter.py` - New module for CSV export:
   - Create `export_contacts_to_csv()` function
   - Define CSV column structure
   - Handle multiple phones/emails/addresses
   - Proper CSV formatting and escaping
   - Apply phone normalization if enabled

4. `./README.md` - Update documentation:
   - Document `--normalize-phones` and `--no-normalize-phones` options
   - Document `--csv` or `--export-csv` option
   - Add examples of usage
   - Explain E.164 format briefly
</output>

<verification>
Before declaring complete, verify:

1. **Phone Normalization**:
   - Test with `--normalize-phones` flag: phones should be in E.164 format in output
   - Test without flag: should prompt user, respect yes/no answer
   - Test with `--no-normalize-phones`: should not normalize, no prompt
   - Test with `--no-confirm`: should default to no normalization, no prompt
   - Verify phone types are preserved after normalization
   - Check invalid phone numbers are handled gracefully (original preserved, warning logged)
   - Verify normalization works in both vCard and CSV outputs

2. **CSV Export**:
   - Test CSV export with `--csv` option
   - Verify all contact fields are included
   - Check multiple phones/emails/addresses are handled correctly
   - Verify CSV formatting (commas, quotes, newlines handled properly)
   - Test CSV opens correctly in spreadsheet applications
   - Verify phone normalization applies to CSV if enabled

3. **Integration**:
   - Test full workflow: parse → detect duplicates → merge → normalize (if enabled) → export vCard → export CSV (if requested)
   - Verify no regression in existing functionality
   - Check validation still works correctly
   - Verify logging includes normalization statistics

4. **Edge Cases**:
   - Contacts with no phone numbers
   - Contacts with invalid phone numbers
   - Contacts with many phones/emails/addresses
   - Special characters in contact data (commas, quotes, newlines)
   - Non-interactive mode (no TTY)

Test by:
- Running the application with various flag combinations
- Checking output files (vCard and CSV) for correct formatting
- Opening CSV in spreadsheet application to verify structure
- Comparing normalized vs non-normalized outputs
</verification>

<success_criteria>
- Phone normalization can be enabled via `--normalize-phones` flag
- Interactive prompt appears when flag is not provided (unless `--no-confirm` is used)
- Phone numbers are normalized to E.164 format in both vCard and CSV outputs when enabled
- Phone type information is preserved after normalization
- CSV export creates properly formatted CSV files with all contact data
- Multiple phones/emails/addresses are handled correctly in CSV
- Invalid phone numbers are handled gracefully (original preserved, warning logged)
- No regression in existing functionality
- Documentation updated with new features
- Code follows existing patterns and style
- All edge cases handled appropriately
</success_criteria>

