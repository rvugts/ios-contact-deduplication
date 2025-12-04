<objective>
Fix blank lines in the output vCard file and ensure it produces valid vCard format, especially when handling Base64-encoded binary data. Additionally, implement validation to parse the output file and verify that no input data was broken or lost during the merge process.
</objective>

<context>
The contact deduplication tool writes merged contacts to a vCard file, but the output contains blank lines which can make the file invalid, particularly when dealing with Base64-encoded binary data (photos, Apple-specific metadata). vCard format specification (RFC 6350) does not allow blank lines within vCard blocks - they can break parsing and corrupt Base64 data.

The current implementation in `src/vcard_parser.py` writes vCard files, but may be introducing blank lines when:
- Writing raw vCard blocks directly
- Serializing vCard objects
- Handling Base64 data with line breaks

We need to:
1. Remove all blank lines from vCard output
2. Ensure proper vCard formatting (no blank lines between fields or within Base64 data)
3. Add validation to parse the output file and compare with input to ensure no data loss

@src/vcard_parser.py - Current vCard writing implementation
@data/output/merged.vcf - Example output file showing blank line issues
</context>

<requirements>

<functional_requirements>
1. **Remove Blank Lines**: Eliminate all blank lines from vCard output:
   - No blank lines between vCard blocks (only between END:VCARD and next BEGIN:VCARD)
   - No blank lines within a vCard block
   - No blank lines within Base64-encoded data fields
   - Preserve proper line folding for long Base64 lines (space/tab continuation)

2. **Valid vCard Format**: Ensure output conforms to vCard 3.0 specification:
   - Each vCard block starts with BEGIN:VCARD and ends with END:VCARD
   - Fields are properly formatted with no blank lines
   - Base64 data is properly encoded without blank lines breaking the encoding
   - Line folding uses space/tab continuation (not blank lines)

3. **Output Validation**: Implement validation that:
   - Parses the output vCard file using the same parser
   - Compares contact count: input contacts vs output contacts
   - Verifies no contacts were lost
   - Checks that all merged contacts are present
   - Validates that Base64 data is preserved correctly
   - Reports any discrepancies or data loss

4. **Error Handling**: If validation fails:
   - Log detailed error information
   - Report which contacts (if any) are missing
   - Provide actionable error messages
</functional_requirements>

<implementation>

<vcard_writing_fixes>
Thoroughly analyze the `write_vcard_file` function and fix blank line issues:

1. **Raw Block Handling**: When writing raw vCard blocks (from `raw_vcard_block` field):
   - Remove all blank lines from the block
   - Preserve line folding (lines starting with space/tab)
   - Ensure proper line endings (single newline between fields)
   - Remove trailing blank lines

2. **Serialized vCard Handling**: When using `vcard.serialize()`:
   - Post-process the serialized output to remove blank lines
   - Ensure no blank lines within Base64 data
   - Maintain proper vCard structure

3. **Base64 Data Handling**: For Base64-encoded fields:
   - Ensure no blank lines break the Base64 encoding
   - Preserve line folding if Base64 data is long (RFC 6350 allows 75 chars per line with continuation)
   - Remove any blank lines that might have been introduced
</vcard_writing_fixes>

<validation_implementation>
Implement a validation function that:

1. **Parse Output File**: Use the existing `parse_vcard_file` function to parse the output
2. **Compare Counts**: 
   - Compare total contact count (input vs output)
   - Account for merged contacts (output should have fewer contacts due to merging)
   - Verify the reduction matches expected merge count

3. **Data Integrity Checks**:
   - Verify all non-duplicate contacts are present
   - Verify all merged contacts are present
   - Check that contacts have required fields (at least name or phone/email)
   - Verify Base64 data fields are preserved (compare presence, not exact content due to encoding)

4. **Reporting**: Generate a validation report showing:
   - Contact count comparison
   - Any missing contacts
   - Any contacts with missing required fields
   - Validation status (pass/fail)
</validation_implementation>

<code_quality>
- Write clean, well-documented code
- Add comprehensive error handling
- Include logging for validation results
- Make validation optional (can be disabled via flag)
- Ensure validation doesn't significantly slow down processing
</code_quality>

</implementation>

<output>
Modify the following files:

1. `./src/vcard_parser.py` - Fix `write_vcard_file` function to remove blank lines and ensure valid vCard format
2. `./src/vcard_parser.py` - Add `validate_vcard_file` function for output validation
3. `./src/main.py` - Integrate validation after writing output file:
   - Add `--validate` flag (default: True)
   - Call validation after writing output
   - Report validation results to user
   - Exit with error code if validation fails (unless `--no-validate` is used)
</output>

<verification>
Before declaring complete, verify:

1. **Blank Lines Removed**: 
   - Check output file has no blank lines within vCard blocks
   - Verify Base64 data is not broken by blank lines
   - Confirm proper line folding is preserved

2. **Valid vCard Format**:
   - Parse output file with vobject to ensure it's valid
   - Verify all vCard blocks start with BEGIN:VCARD and end with END:VCARD
   - Check that no blank lines exist between fields

3. **Validation Works**:
   - Run validation on a test output file
   - Verify it correctly identifies contact count matches
   - Test with a file that has issues to ensure validation catches problems
   - Verify validation reports are clear and actionable

4. **No Data Loss**:
   - Compare input and output contact counts (accounting for merges)
   - Verify all expected contacts are present
   - Check that Base64 data fields are preserved

Test by:
- Running the application on the existing contact file
- Checking the output file for blank lines
- Running validation and verifying it reports correctly
- Parsing the output file to ensure it's valid
</verification>

<success_criteria>
- Output vCard file contains no blank lines within vCard blocks
- Output file is valid vCard format and can be parsed successfully
- Base64-encoded data is preserved correctly without blank lines breaking encoding
- Validation function successfully parses output and verifies no data loss
- Validation reports are clear and actionable
- All contacts from input are accounted for in output (accounting for merges)
- Code handles edge cases gracefully (empty files, malformed data, etc.)
</success_criteria>

