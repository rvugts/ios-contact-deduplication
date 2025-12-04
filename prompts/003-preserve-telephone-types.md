<objective>
Fix the issue where telephone types (home, cell, work, etc.) are being lost during contact merging. Ensure that all telephone type information from the input vCard file is preserved in the output, staying as close as possible to the original input data.
</objective>

<context>
The contact deduplication tool is losing telephone type information (home, cell, work, mobile, etc.) in some cases, possibly only when contacts are merged. Telephone types are important metadata that help users distinguish between different phone numbers for the same contact (e.g., work vs personal numbers).

The issue likely occurs in one or more of these areas:
1. **Parsing**: Phone types may not be correctly extracted from the input vCard
2. **Merging**: Phone types may be lost when merging duplicate contacts
3. **Writing**: Phone types may not be correctly written to the output vCard

vCard format supports phone types via the TYPE parameter (e.g., `TEL;TYPE=CELL:+1234567890` or `TEL;TYPE=HOME,VOICE:+1234567890`). These types must be preserved throughout the entire pipeline.

@src/vcard_parser.py - Phone parsing and vCard writing logic
@src/contact_merger.py - Contact merging logic, especially phone number merging
@data/input/contacts.vcf - Input file to check for phone types
@data/output/merged.vcf - Output file to verify types are preserved
</context>

<requirements>

<functional_requirements>
1. **Preserve All Phone Types**: Ensure all telephone type information is preserved:
   - Parse all TYPE parameters from input vCards (CELL, HOME, WORK, MOBILE, VOICE, FAX, etc.)
   - Store phone types correctly in the contact dictionary structure
   - Preserve types when merging contacts (combine unique phone+type combinations)
   - Write types correctly to output vCard file

2. **Investigate Root Cause**: Thoroughly analyze where types are being lost:
   - Check parsing logic: Are types extracted from `TEL;TYPE=...` fields?
   - Check merging logic: Are types preserved when combining phone numbers?
   - Check writing logic: Are types written correctly to output vCard?
   - Compare input vs output to identify specific cases where types are lost

3. **Fix All Issues**: Address any problems found:
   - Fix parsing if types aren't being extracted
   - Fix merging if types are lost during combination
   - Fix writing if types aren't being serialized correctly
   - Ensure backward compatibility with existing code

4. **Validation**: Add verification that types are preserved:
   - Compare phone types in input vs output
   - Log any cases where types are lost
   - Report statistics on type preservation
</functional_requirements>

<implementation>

<investigation_approach>
1. **Examine Current Implementation**:
   - Review `_parse_single_vcard` function to see how phone types are extracted
   - Review `_merge_two_contacts` in ContactMerger to see how phones are merged
   - Review `_contact_to_vcard` to see how phones are written back
   - Check if phone types are stored as part of phone dictionary structure

2. **Test with Real Data**:
   - Parse a sample contact with multiple phone types from input file
   - Trace through the entire pipeline (parse → merge → write)
   - Compare input and output to identify where types are lost

3. **Fix Issues Found**:
   - Update parsing to correctly extract all TYPE parameters
   - Update merging to preserve types when combining phones
   - Update writing to correctly serialize types back to vCard format
</investigation_approach>

<phone_type_handling>
Phone types in vCard format can be:
- Single type: `TEL;TYPE=CELL:+1234567890`
- Multiple types: `TEL;TYPE=HOME,VOICE:+1234567890`
- Type parameters: `TEL;TYPE=WORK;TYPE=VOICE:+1234567890`

The implementation must:
- Extract all types (not just the first one)
- Store types as a list or comma-separated string
- Preserve all types when merging (don't combine phones with same number but different types)
- Write types back in correct vCard format
</phone_type_handling>

<code_quality>
- Maintain existing code structure and patterns
- Add comprehensive logging for type preservation
- Handle edge cases (phones without types, multiple types, etc.)
- Ensure no regression in other functionality
- Add comments explaining type preservation logic
</code_quality>

</implementation>

<output>
Modify the following files as needed:

1. `./src/vcard_parser.py` - Fix phone type parsing and writing:
   - Ensure `_parse_single_vcard` extracts all TYPE parameters from TEL fields
   - Ensure `_contact_to_vcard` writes TYPE parameters correctly
   - Update phone dictionary structure if needed to store types properly

2. `./src/contact_merger.py` - Fix phone type preservation during merging:
   - Ensure `_merge_two_contacts` preserves phone types when combining
   - Treat phones with same number but different types as distinct
   - Combine phones intelligently without losing type information

3. `./src/vcard_parser.py` - Add validation/logging:
   - Log phone type information during parsing
   - Compare input vs output phone types during validation
   - Report any type loss in validation report
</output>

<verification>
Before declaring complete, verify:

1. **Type Preservation**:
   - Parse input file and verify all phone types are extracted
   - Check merged contacts have all phone types from source contacts
   - Verify output file contains all phone types from input
   - Compare a few specific contacts: input vs output phone types

2. **No Regression**:
   - Run full deduplication process
   - Verify all contacts are still processed correctly
   - Verify no other functionality is broken
   - Check validation still passes

3. **Edge Cases**:
   - Phones without types (should still work)
   - Phones with multiple types (all should be preserved)
   - Merged contacts with overlapping phone numbers but different types

Test by:
- Running the application on the contact file
- Comparing phone types in input vs output for a few contacts
- Checking merged contacts specifically to ensure types are preserved
- Verifying validation reports show no type loss
</verification>

<success_criteria>
- All phone types from input vCard are preserved in output vCard
- Phone types are correctly extracted during parsing
- Phone types are preserved when merging contacts
- Phone types are correctly written to output vCard format
- Validation confirms no type loss
- No regression in other functionality
- Code handles edge cases (no types, multiple types, etc.)
</success_criteria>

