"""
vCard file parsing module for reading and writing vCard format contacts.
"""

import vobject
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("contact_deduplication")


def _split_vcard_blocks(content: str) -> List[str]:
    """
    Split vCard content into individual vCard blocks.
    
    Args:
        content: Full vCard file content
    
    Returns:
        List of individual vCard block strings
    """
    blocks = []
    current_block = []
    in_block = False
    
    # Handle both \r\n and \n line endings
    lines = content.replace('\r\n', '\n').split('\n')
    
    for line in lines:
        line_upper = line.strip().upper()
        
        # vCard blocks start with BEGIN:VCARD
        if 'BEGIN:VCARD' in line_upper:
            # If we were in a block, save it (shouldn't happen in valid files, but handle it)
            if in_block and current_block:
                blocks.append('\n'.join(current_block))
            current_block = [line]
            in_block = True
        elif in_block:
            current_block.append(line)
            # vCard blocks end with END:VCARD
            if 'END:VCARD' in line_upper:
                blocks.append('\n'.join(current_block))
                current_block = []
                in_block = False
    
    # Add any remaining block (incomplete vCard)
    if in_block and current_block:
        blocks.append('\n'.join(current_block))
    
    return blocks


def parse_vcard_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parse a vCard file and extract all contacts.
    
    Args:
        file_path: Path to the .vcf file
    
    Returns:
        List of contact dictionaries with normalized field names
    
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is malformed or empty
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    contacts = []
    
    try:
        # Try reading as text first
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, try with error handling
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        
        # Always use block-by-block parsing to preserve raw vCard blocks with binary data
        # This ensures photos and Base64 data are preserved
        vcard_blocks = _split_vcard_blocks(content)
        logger.info(f"Split file into {len(vcard_blocks)} vCard blocks")
        
        # Try bulk parsing first to see if it works, but we'll still use blocks for raw data
        try:
            # Test if bulk parsing works (for validation)
            test_vcards = list(vobject.readComponents(content))
            # If it works, we'll use block-by-block with raw blocks preserved
        except Exception as e:
            # Bulk parsing failed, will use block-by-block with manual fallback
            logger.info(f"Bulk parsing test failed, will use block-by-block parsing: {e}")
        
        # Always parse block-by-block to preserve raw_vcard_block (critical for binary data)
        parsed_count = 0
        failed_count = 0
        
        for block_num, block in enumerate(vcard_blocks, 1):
            block_parsed = False
            try:
                # Parse single vCard block
                vcards = list(vobject.readComponents(block))
                for vcard in vcards:
                    try:
                        # CRITICAL: Always pass raw block to preserve binary data (photos, Base64)
                        # The raw block contains the original vCard with all binary data intact
                        contact = _parse_single_vcard(vcard, raw_block=block)
                        if contact:
                            # Ensure raw_vcard_block is set (critical for binary data preservation)
                            if 'raw_vcard_block' not in contact or not contact['raw_vcard_block']:
                                contact['raw_vcard_block'] = block
                            contacts.append(contact)
                            parsed_count += 1
                            block_parsed = True
                    except Exception as e:
                        logger.debug(f"Error parsing vCard entry in block {block_num}: {e}")
                        continue
                
                # If vobject parsed but didn't yield any contacts, try manual parsing
                if not block_parsed:
                    logger.debug(f"vobject parsed block {block_num} but yielded no contacts, trying manual extraction")
                    contact = _parse_vcard_manually(block, block_num)
                    if contact:
                        # Ensure raw_vcard_block is preserved
                        if 'raw_vcard_block' not in contact or not contact['raw_vcard_block']:
                            contact['raw_vcard_block'] = block
                        contacts.append(contact)
                        parsed_count += 1
                        block_parsed = True
                        
            except Exception as e:
                    # If vobject fails, try to extract basic info manually and preserve raw block
                    logger.debug(f"vobject parsing failed for block {block_num}, attempting manual extraction: {e}")
                    contact = _parse_vcard_manually(block, block_num)
                    if contact:
                        # Ensure raw_vcard_block is preserved
                        if 'raw_vcard_block' not in contact or not contact['raw_vcard_block']:
                            contact['raw_vcard_block'] = block
                        contacts.append(contact)
                        parsed_count += 1
                    else:
                        failed_count += 1
                        # Try one more time - create a minimal contact with just the raw block
                        if 'BEGIN:VCARD' in block.upper() and 'END:VCARD' in block.upper():
                            minimal_contact = {
                                'name': f'Contact {block_num}',
                                'first_name': '',
                                'last_name': '',
                                'middle_name': '',
                                'prefix': '',
                                'suffix': '',
                                'phones': [],
                                'emails': [],
                                'addresses': [],
                                'urls': [],
                                'organization': '',
                                'title': '',
                                'department': '',
                                'notes': [],
                                'birthday': None,
                                'anniversary': None,
                                'photo': None,
                                'custom_fields': {},
                                'raw_vcard_block': block  # CRITICAL: Preserve raw block for binary data
                            }
                            contacts.append(minimal_contact)
                            parsed_count += 1
                            logger.debug(f"Created minimal contact from block {block_num} using raw block")
                        else:
                            logger.warning(f"Block {block_num} missing BEGIN/END markers. Skipping.")
                    continue
            
            if failed_count > 0:
                logger.warning(f"Failed to parse {failed_count} out of {len(vcard_blocks)} vCard blocks")
        
        if not contacts:
            raise ValueError(f"No valid contacts found in {file_path}")
        
        logger.info(f"Successfully parsed {len(contacts)} contacts from {file_path}")
        return contacts
        
    except Exception as e:
        logger.error(f"Error reading vCard file {file_path}: {e}")
        raise


def _parse_vcard_manually(vcard_block: str, block_num: int) -> Optional[Dict[str, Any]]:
    """
    Manually parse a vCard block when vobject fails (e.g., due to Base64 binary data).
    Extracts essential fields for duplicate detection while preserving raw vCard.
    
    Args:
        vcard_block: Raw vCard block string
        block_num: Block number for logging
    
    Returns:
        Contact dictionary with basic fields and raw vCard preserved, or None if invalid
    """
    contact = {
        'name': '',
        'first_name': '',
        'last_name': '',
        'middle_name': '',
        'prefix': '',
        'suffix': '',
        'phones': [],
        'emails': [],
        'addresses': [],
        'urls': [],
        'organization': '',
        'title': '',
        'department': '',
        'notes': [],
        'birthday': None,
        'anniversary': None,
        'photo': None,
        'custom_fields': {},
        'raw_vcard_block': vcard_block  # Preserve raw block for writing back
    }
    
    # Normalize line endings and split
    lines = vcard_block.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    current_field = None
    current_value_parts = []
    
    for line in lines:
        # Handle folded lines (lines starting with space or tab) - vCard spec allows this
        if line.startswith(' ') or line.startswith('\t'):
            if current_field and current_value_parts:
                # Append folded content (remove leading whitespace)
                current_value_parts.append(line.lstrip())
            continue
        
        # Process previous field if any
        if current_field:
            full_value = ''.join(current_value_parts)
            if full_value:  # Only process if we have a value
                _process_manual_field(contact, current_field, full_value)
            current_field = None
            current_value_parts = []
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Parse new field
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                field_part = parts[0].strip()
                value_part = parts[1]
                
                # Extract field name (before semicolon if params exist)
                field_name = field_part.split(';')[0].upper()
                # Skip version and prodid
                if field_name in ['VERSION', 'PRODID', 'BEGIN', 'END']:
                    continue
                
                current_field = field_name
                current_value_parts = [value_part]
    
    # Process last field
    if current_field and current_value_parts:
        full_value = ''.join(current_value_parts)
        if full_value:
            _process_manual_field(contact, current_field, full_value)
    
    # Always preserve the raw vCard block - this is critical for binary data (photos, Base64)
    # The raw block contains ALL original data including Base64-encoded binary content
    # We'll use the raw block when writing back to preserve everything
    # If we couldn't extract a name, try to generate one from the raw block
    original_name = contact['name']
    name_was_placeholder = original_name.startswith('Contact ') if original_name else False
    name_was_empty = not original_name
    
    if not contact['name'] or contact['name'].startswith('Contact '):
        # Look for FN: field in the raw block (handle folded lines)
        lines = contact['raw_vcard_block'].split('\n')
        current_fn = None
        for line in lines:
            line_upper = line.strip().upper()
            if line_upper.startswith('FN:'):
                current_fn = line.split(':', 1)[1] if ':' in line else ''
            elif current_fn is not None and (line.startswith(' ') or line.startswith('\t')):
                # Continuation of FN field
                current_fn += line.lstrip()
            elif current_fn is not None:
                # End of FN field
                contact['name'] = current_fn.strip()
                break
        
        # If we extracted from FN field, log it (use WARNING level to make it more visible)
        if contact['name'] and contact['name'] != original_name and (name_was_placeholder or name_was_empty):
            logger.warning(f"Contact {block_num}: Name was {'empty' if name_was_empty else 'placeholder (' + original_name + ')'}, extracted from vCard FN field: {contact['name']}")
        
        # If still no name, try using organization name (use WARNING level to make it more visible)
        if (not contact['name'] or contact['name'].startswith('Contact ')) and contact.get('organization'):
            contact['name'] = contact['organization']
            if name_was_placeholder or name_was_empty:
                logger.warning(f"Contact {block_num}: Name was {'empty' if name_was_empty else 'placeholder (' + original_name + ')'}, using organization name: {contact['name']}")
        
        # If still no name, use a placeholder (but this should be rare)
        if not contact['name'] or contact['name'].startswith('Contact '):
            new_name = f'Contact {block_num}'
            if contact['name'] != new_name:
                logger.warning(f"Contact {block_num}: Name was {'empty' if name_was_empty else 'placeholder (' + original_name + ')'}, assigned placeholder: {new_name}")
            contact['name'] = new_name
    
    # Always return contact if we have a raw block
    return contact


def _process_manual_field(contact: Dict[str, Any], field_name: str, value: str) -> None:
    """
    Process a manually extracted vCard field.
    
    Args:
        contact: Contact dictionary to update
        field_name: Field name (e.g., 'FN', 'TEL', 'EMAIL')
        value: Field value
    """
    if field_name == 'FN':
        contact['name'] = value
    elif field_name == 'N':
        # Name field: Family;Given;Additional;Prefix;Suffix
        parts = value.split(';')
        if len(parts) >= 1:
            contact['last_name'] = parts[0]
        if len(parts) >= 2:
            contact['first_name'] = parts[1]
        if len(parts) >= 3:
            contact['middle_name'] = parts[2]
        if len(parts) >= 4:
            contact['prefix'] = parts[3]
        if len(parts) >= 5:
            contact['suffix'] = parts[4]
    elif field_name == 'TEL':
        contact['phones'].append({'number': value, 'type': 'OTHER'})
    elif field_name == 'EMAIL':
        contact['emails'].append({'address': value, 'type': 'OTHER'})
    elif field_name == 'ORG':
        parts = value.split(';')
        if len(parts) >= 1:
            contact['organization'] = parts[0]
        if len(parts) >= 2:
            contact['department'] = parts[1]
    elif field_name == 'TITLE':
        contact['title'] = value
    elif field_name == 'NOTE':
        contact['notes'].append(value)
    elif field_name == 'BDAY':
        contact['birthday'] = value
    elif field_name == 'ANNIVERSARY':
        contact['anniversary'] = value
    elif field_name == 'PHOTO':
        # Preserve photo data (may be Base64)
        contact['photo'] = value
    elif field_name.startswith('X-') or field_name.startswith('ITEM'):
        # Preserve all X-* and ITEM* fields (Apple-specific)
        if field_name not in contact['custom_fields']:
            contact['custom_fields'][field_name] = []
        contact['custom_fields'][field_name].append({'value': value, 'serialized': f"{field_name}:{value}"})


def _parse_single_vcard(vcard: vobject.base.Component, raw_block: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Parse a single vCard object into a contact dictionary.
    
    Args:
        vcard: vobject vCard component
        raw_block: Optional raw vCard block string (preserves binary data)
    
    Returns:
        Contact dictionary or None if invalid
    """
    contact = {
        'name': '',
        'first_name': '',
        'last_name': '',
        'middle_name': '',
        'prefix': '',
        'suffix': '',
        'phones': [],
        'emails': [],
        'addresses': [],
        'urls': [],
        'organization': '',
        'title': '',
        'department': '',
        'notes': [],
        'birthday': None,
        'anniversary': None,
        'photo': None,
        'custom_fields': {},
        'raw_vcard': vcard
    }
    
    # Preserve raw vCard block if provided (critical for binary data)
    if raw_block:
        contact['raw_vcard_block'] = raw_block
    
    # Name parsing
    if hasattr(vcard, 'n'):
        name_parts = vcard.n.value
        contact['last_name'] = name_parts.family or ''
        contact['first_name'] = name_parts.given or ''
        contact['middle_name'] = name_parts.additional or ''
        contact['prefix'] = name_parts.prefix or ''
        contact['suffix'] = name_parts.suffix or ''
        
        # Construct full name
        name_parts_list = [
            contact['prefix'],
            contact['first_name'],
            contact['middle_name'],
            contact['last_name'],
            contact['suffix']
        ]
        contact['name'] = ' '.join(filter(None, name_parts_list)).strip()
    
    # Formatted name (FN field)
    if hasattr(vcard, 'fn'):
        if not contact['name']:
            contact['name'] = vcard.fn.value
    
    # Phone numbers
    if hasattr(vcard, 'tel_list'):
        for tel in vcard.tel_list:
            # Extract TYPE parameters from params dict (vobject stores them here)
            types = []
            if hasattr(tel, 'params') and tel.params:
                type_params = tel.params.get('TYPE', [])
                if isinstance(type_params, list):
                    types = [str(t).upper() for t in type_params]
                elif type_params:
                    types = [str(type_params).upper()]
            
            phone_info = {
                'number': tel.value,
                'type': ','.join(types) if types else 'OTHER'
            }
            contact['phones'].append(phone_info)
    
    # Email addresses
    if hasattr(vcard, 'email_list'):
        for email in vcard.email_list:
            email_info = {
                'address': email.value,
                'type': ','.join(email.type_param_list) if hasattr(email, 'type_param_list') else 'OTHER'
            }
            contact['emails'].append(email_info)
    
    # Addresses
    if hasattr(vcard, 'adr_list'):
        for adr in vcard.adr_list:
            addr_parts = adr.value
            # vobject address objects have different attribute access
            if isinstance(addr_parts, (list, tuple)) and len(addr_parts) >= 7:
                address_info = {
                    'type': ','.join(adr.type_param_list) if hasattr(adr, 'type_param_list') else 'OTHER',
                    'street': addr_parts[2] if len(addr_parts) > 2 else '',
                    'city': addr_parts[3] if len(addr_parts) > 3 else '',
                    'region': addr_parts[4] if len(addr_parts) > 4 else '',
                    'postal_code': addr_parts[5] if len(addr_parts) > 5 else '',
                    'country': addr_parts[6] if len(addr_parts) > 6 else ''
                }
            else:
                # Fallback for different address formats
                address_info = {
                    'type': ','.join(adr.type_param_list) if hasattr(adr, 'type_param_list') else 'OTHER',
                    'street': str(addr_parts[2]) if isinstance(addr_parts, (list, tuple)) and len(addr_parts) > 2 else '',
                    'city': str(addr_parts[3]) if isinstance(addr_parts, (list, tuple)) and len(addr_parts) > 3 else '',
                    'region': str(addr_parts[4]) if isinstance(addr_parts, (list, tuple)) and len(addr_parts) > 4 else '',
                    'postal_code': str(addr_parts[5]) if isinstance(addr_parts, (list, tuple)) and len(addr_parts) > 5 else '',
                    'country': str(addr_parts[6]) if isinstance(addr_parts, (list, tuple)) and len(addr_parts) > 6 else ''
                }
            contact['addresses'].append(address_info)
    
    # URLs
    if hasattr(vcard, 'url_list'):
        for url in vcard.url_list:
            contact['urls'].append(url.value)
    
    # Organization
    if hasattr(vcard, 'org'):
        org_parts = vcard.org.value
        if isinstance(org_parts, list) and len(org_parts) > 0:
            contact['organization'] = org_parts[0]
            if len(org_parts) > 1:
                contact['department'] = org_parts[1]
    
    # Title
    if hasattr(vcard, 'title'):
        contact['title'] = vcard.title.value
    
    # Notes
    if hasattr(vcard, 'note_list'):
        for note in vcard.note_list:
            contact['notes'].append(note.value)
    
    # Birthday
    if hasattr(vcard, 'bday'):
        contact['birthday'] = vcard.bday.value
    
    # Anniversary
    if hasattr(vcard, 'anniversary'):
        contact['anniversary'] = vcard.anniversary.value
    
    # Photo
    if hasattr(vcard, 'photo'):
        contact['photo'] = vcard.photo.value
    
    # Custom fields (any other fields) - preserve all X-AB* and itemX.* fields
    for key in vcard.contents:
        if key not in ['n', 'fn', 'tel', 'email', 'adr', 'url', 'org', 'title', 
                       'note', 'bday', 'anniversary', 'photo', 'version', 'prodid']:
            if key not in contact['custom_fields']:
                contact['custom_fields'][key] = []
            for item in vcard.contents[key]:
                # Preserve the full item with all its properties (including Base64 data)
                field_data = {
                    'value': item.value,
                    'params': {}
                }
                # Preserve all parameters (like encoding, type, etc.)
                if hasattr(item, 'params'):
                    field_data['params'] = dict(item.params)
                # Also store the serialized version to preserve exact format
                try:
                    field_data['serialized'] = item.serialize()
                except:
                    # If serialization fails, just store the value
                    pass
                contact['custom_fields'][key].append(field_data)
    
    return contact


def _clean_vcard_block(block: str) -> str:
    """
    Remove blank lines from a vCard block while preserving line folding.
    
    Args:
        block: Raw vCard block string
    
    Returns:
        Cleaned vCard block with no blank lines
    """
    lines = block.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Keep non-blank lines
        if line.strip():
            cleaned_lines.append(line)
        # Also keep lines that are line continuations (start with space/tab)
        # This preserves proper vCard line folding
        elif line.startswith(' ') or line.startswith('\t'):
            cleaned_lines.append(line)
        # Skip blank lines
    
    # Join with newlines, ensuring no double newlines
    cleaned_block = '\n'.join(cleaned_lines)
    
    # Remove any trailing newlines
    cleaned_block = cleaned_block.rstrip('\n\r')
    
    return cleaned_block


def write_vcard_file(contacts: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Write contacts to a vCard file.
    
    Args:
        contacts: List of contact dictionaries
        output_path: Path where the vCard file should be written
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    vcard_strings = []
    
    for contact in contacts:
        try:
            # Always use raw_vcard_block if available (preserves all binary data including photos)
            # Since we now always preserve raw_vcard_block during parsing, this should always be available
            if 'raw_vcard_block' in contact and contact['raw_vcard_block']:
                cleaned_block = _clean_vcard_block(contact['raw_vcard_block'])
                vcard_strings.append(cleaned_block)
            else:
                # Fallback: construct from parsed data (should rarely happen now)
                # This preserves the contact even if raw_vcard_block is missing
                logger.warning(f"Contact {contact.get('name', 'Unknown')} missing raw_vcard_block, using serialization fallback")
                try:
                    vcard = _contact_to_vcard(contact)
                    serialized = vcard.serialize()
                    cleaned_block = _clean_vcard_block(serialized)
                    vcard_strings.append(cleaned_block)
                except Exception as serialize_error:
                    logger.error(f"Failed to serialize contact {contact.get('name', 'Unknown')}: {serialize_error}")
                    # Contact will be missing from output - this should not happen with proper raw_vcard_block preservation
        except Exception as e:
            logger.error(f"Unexpected error processing contact {contact.get('name', 'Unknown')}: {e}")
            # Try raw_vcard_block as last resort
            if 'raw_vcard_block' in contact and contact['raw_vcard_block']:
                try:
                    cleaned_block = _clean_vcard_block(contact['raw_vcard_block'])
                    vcard_strings.append(cleaned_block)
                except Exception:
                    logger.error(f"Could not write raw_vcard_block for {contact.get('name', 'Unknown')}, contact will be lost")
            else:
                logger.error(f"No raw_vcard_block available for {contact.get('name', 'Unknown')}, contact will be lost")
    
    # Join vCard blocks with double newline (one blank line between blocks is acceptable)
    # But ensure no blank lines within blocks
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(vcard_strings))
        if vcard_strings:  # Add final newline if we wrote anything
            f.write('\n')
    
    logger.info(f"Successfully wrote {len(contacts)} contacts to {output_path}")


def validate_vcard_file(
    output_path: Path,
    expected_contact_count: int,
    input_contact_count: int,
    duplicate_groups_count: int
) -> tuple[bool, Dict[str, Any]]:
    """
    Validate the output vCard file to ensure no data was lost.
    
    Args:
        output_path: Path to the output vCard file
        expected_contact_count: Expected number of contacts in output (after merging)
        input_contact_count: Original number of contacts in input
        duplicate_groups_count: Number of duplicate groups that were merged
    
    Returns:
        Tuple of (is_valid, validation_report_dict)
    """
    report = {
        'valid': False,
        'output_contact_count': 0,
        'expected_contact_count': expected_contact_count,
        'input_contact_count': input_contact_count,
        'duplicate_groups_count': duplicate_groups_count,
        'contacts_lost': 0,
        'parse_successful': False,
        'errors': [],
        'warnings': []
    }
    
    if not output_path.exists():
        report['errors'].append(f"Output file does not exist: {output_path}")
        return False, report
    
    try:
        # Try to parse the output file
        output_contacts = parse_vcard_file(output_path)
        report['parse_successful'] = True
        report['output_contact_count'] = len(output_contacts)
        
        # Check contact count
        if len(output_contacts) != expected_contact_count:
            report['errors'].append(
                f"Contact count mismatch: expected {expected_contact_count}, got {len(output_contacts)}"
            )
            report['contacts_lost'] = expected_contact_count - len(output_contacts)
        else:
            logger.info(f"Validation: Contact count matches expected ({expected_contact_count})")
        
        # Verify all contacts have required fields
        contacts_without_name = []
        contacts_without_data = []
        
        # Check phone type preservation
        total_phones_with_types = 0
        phones_with_types = 0
        
        for i, contact in enumerate(output_contacts, 1):
            has_name = bool(contact.get('name') and not contact.get('name', '').startswith('Contact '))
            has_phone = bool(contact.get('phones'))
            has_email = bool(contact.get('emails'))
            has_org = bool(contact.get('organization'))
            
            if not has_name:
                contacts_without_name.append(i)
            
            if not (has_name or has_phone or has_email or has_org):
                contacts_without_data.append(i)
            
            # Count phones with types
            for phone in contact.get('phones', []):
                total_phones_with_types += 1
                if phone.get('type') and phone['type'] != 'OTHER':
                    phones_with_types += 1
        
        if contacts_without_name:
            report['warnings'].append(
                f"Found {len(contacts_without_name)} contacts without proper names (indices: {contacts_without_name[:10]})"
            )
        
        if contacts_without_data:
            report['errors'].append(
                f"Found {len(contacts_without_data)} contacts without any data (indices: {contacts_without_data[:10]})"
            )
        
        # Report phone type preservation
        if total_phones_with_types > 0:
            type_preservation_percent = (phones_with_types / total_phones_with_types * 100) if total_phones_with_types > 0 else 0
            report['phone_types'] = {
                'total_phones': total_phones_with_types,
                'phones_with_types': phones_with_types,
                'preservation_percent': type_preservation_percent
            }
            logger.info(f"Phone type preservation: {phones_with_types}/{total_phones_with_types} phones have types ({type_preservation_percent:.1f}%)")
        
        # Check for blank lines in the file (should not exist within vCard blocks)
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
            # Check for blank lines within vCard blocks
            in_vcard = False
            blank_lines_in_block = []
            current_block_start = 0
            
            for i, line in enumerate(lines, 1):
                if line.strip().upper() == 'BEGIN:VCARD':
                    in_vcard = True
                    current_block_start = i
                elif line.strip().upper() == 'END:VCARD':
                    if in_vcard:
                        in_vcard = False
                elif in_vcard and not line.strip() and not (line.startswith(' ') or line.startswith('\t')):
                    # Blank line within vCard block (not a continuation line)
                    blank_lines_in_block.append(i)
            
            if blank_lines_in_block:
                report['errors'].append(
                    f"Found {len(blank_lines_in_block)} blank lines within vCard blocks (lines: {blank_lines_in_block[:10]})"
                )
        
        # Determine if validation passed
        report['valid'] = len(report['errors']) == 0 and report['parse_successful']
        
        if report['valid']:
            logger.info("Validation passed: Output file is valid and all contacts are present")
        else:
            logger.warning(f"Validation failed: {len(report['errors'])} errors found")
        
        return report['valid'], report
        
    except Exception as e:
        report['errors'].append(f"Failed to parse output file: {e}")
        logger.error(f"Validation error: {e}")
        return False, report




def _contact_to_vcard(contact: Dict[str, Any]) -> vobject.base.Component:
    """
    Convert a contact dictionary to a vCard object.
    
    Args:
        contact: Contact dictionary
    
    Returns:
        vobject vCard component
    """
    vcard = vobject.vCard()
    
    # Name
    if contact.get('first_name') or contact.get('last_name'):
        n = vcard.add('n')
        n.value = vobject.vcard.Name(
            family=contact.get('last_name', ''),
            given=contact.get('first_name', ''),
            additional=contact.get('middle_name', ''),
            prefix=contact.get('prefix', ''),
            suffix=contact.get('suffix', '')
        )
    
    # Formatted name (required by vCard spec)
    if contact.get('name'):
        vcard.add('fn').value = contact['name']
    elif contact.get('first_name') or contact.get('last_name'):
        # Generate name from parts if not provided
        name_parts = [
            contact.get('prefix', ''),
            contact.get('first_name', ''),
            contact.get('middle_name', ''),
            contact.get('last_name', ''),
            contact.get('suffix', '')
        ]
        generated_name = ' '.join(filter(None, name_parts)).strip()
        if generated_name:
            vcard.add('fn').value = generated_name
        else:
            vcard.add('fn').value = 'Unknown'
    else:
        # Fallback if no name at all
        vcard.add('fn').value = 'Unknown'
    
    # Phone numbers
    for phone in contact.get('phones', []):
        tel = vcard.add('tel')
        tel.value = phone['number']
        if phone.get('type') and phone['type'] != 'OTHER':
            # Handle multiple types (comma-separated or list)
            phone_type = phone['type']
            if isinstance(phone_type, str):
                # Split comma-separated types
                types = [t.strip().upper() for t in phone_type.split(',') if t.strip()]
            elif isinstance(phone_type, list):
                types = [str(t).upper() for t in phone_type if t]
            else:
                types = [str(phone_type).upper()]
            
            # Set TYPE parameter (vobject expects it in params)
            if types:
                tel.params['TYPE'] = types
    
    # Email addresses
    for email in contact.get('emails', []):
        email_obj = vcard.add('email')
        email_obj.value = email['address']
        if email.get('type'):
            email_obj.type_param = email['type']
    
    # Addresses
    for addr in contact.get('addresses', []):
        adr = vcard.add('adr')
        adr.value = vobject.vcard.Address(
            street=addr.get('street', ''),
            city=addr.get('city', ''),
            region=addr.get('region', ''),
            code=addr.get('postal_code', ''),
            country=addr.get('country', '')
        )
        if addr.get('type'):
            adr.type_param = addr['type']
    
    # URLs
    for url in contact.get('urls', []):
        vcard.add('url').value = url
    
    # Organization
    if contact.get('organization'):
        org = vcard.add('org')
        org_parts = [contact['organization']]
        if contact.get('department'):
            org_parts.append(contact['department'])
        org.value = org_parts
    
    # Title
    if contact.get('title'):
        vcard.add('title').value = contact['title']
    
    # Notes
    for note in contact.get('notes', []):
        vcard.add('note').value = note
    
    # Birthday
    if contact.get('birthday'):
        vcard.add('bday').value = contact['birthday']
    
    # Anniversary
    if contact.get('anniversary'):
        vcard.add('anniversary').value = contact['anniversary']
    
    # Photo - Note: Photos with binary data are preserved via raw_vcard_block
    # This code path is only used as a fallback when raw_vcard_block is not available
    if contact.get('photo'):
        try:
            vcard.add('photo').value = contact['photo']
        except Exception:
            # Skip photo if it causes serialization issues (will be preserved in raw_vcard_block)
            pass
    
    # Custom fields - handle both simple values and structured data
    for field_name, field_values in contact.get('custom_fields', {}).items():
        for field_data in field_values:
            if isinstance(field_data, dict):
                # Structured field data (from manual parsing)
                if 'serialized' in field_data:
                    # Use serialized version if available (preserves exact format)
                    # Note: vobject doesn't support direct serialization injection,
                    # so we'll need to add the field and try to set params
                    field_obj = vcard.add(field_name)
                    field_obj.value = field_data['value']
                    if 'params' in field_data and field_data['params']:
                        for param_key, param_value in field_data['params'].items():
                            setattr(field_obj, param_key, param_value)
                else:
                    field_obj = vcard.add(field_name)
                    field_obj.value = field_data['value']
            else:
                # Simple value
                vcard.add(field_name).value = field_data
    
    return vcard

