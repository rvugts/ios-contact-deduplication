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
        
        # Try parsing all at once first (faster for valid files)
        try:
            vcards = vobject.readComponents(content)
            for vcard in vcards:
                try:
                    contact = _parse_single_vcard(vcard)
                    if contact:
                        contacts.append(contact)
                except Exception as e:
                    logger.warning(f"Error parsing vCard entry: {e}")
                    continue
        except Exception as e:
            # If bulk parsing fails, try parsing block by block
            logger.info(f"Bulk parsing failed, trying block-by-block parsing: {e}")
            vcard_blocks = _split_vcard_blocks(content)
            logger.info(f"Split file into {len(vcard_blocks)} vCard blocks")
            
            parsed_count = 0
            failed_count = 0
            
            for block_num, block in enumerate(vcard_blocks, 1):
                block_parsed = False
                try:
                    # Parse single vCard block
                    vcards = list(vobject.readComponents(block))
                    for vcard in vcards:
                        try:
                            contact = _parse_single_vcard(vcard)
                            if contact:
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
                            contacts.append(contact)
                            parsed_count += 1
                            block_parsed = True
                            
                except Exception as e:
                    # If vobject fails, try to extract basic info manually and preserve raw block
                    logger.debug(f"vobject parsing failed for block {block_num}, attempting manual extraction: {e}")
                    contact = _parse_vcard_manually(block, block_num)
                    if contact:
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
                                'raw_vcard_block': block
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
    
    # Always return the contact if we have a raw block, even if we couldn't extract fields
    # This preserves the contact data even if parsing fails
    # We'll use the raw block when writing back
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


def _parse_single_vcard(vcard: vobject.base.Component) -> Optional[Dict[str, Any]]:
    """
    Parse a single vCard object into a contact dictionary.
    
    Args:
        vcard: vobject vCard component
    
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
            phone_info = {
                'number': tel.value,
                'type': ','.join(tel.type_param_list) if hasattr(tel, 'type_param_list') else 'OTHER'
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
            address_info = {
                'type': ','.join(adr.type_param_list) if hasattr(adr, 'type_param_list') else 'OTHER',
                'street': addr.street or '',
                'city': addr.city or '',
                'region': addr.region or '',
                'postal_code': addr.code or '',
                'country': addr.country or ''
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
            # If we have raw vCard block, use it directly (preserves Base64 data)
            if 'raw_vcard_block' in contact and contact['raw_vcard_block']:
                vcard_strings.append(contact['raw_vcard_block'])
            else:
                # Otherwise, construct from parsed data
                vcard = _contact_to_vcard(contact)
                vcard_strings.append(vcard.serialize())
        except Exception as e:
            logger.warning(f"Error serializing contact {contact.get('name', 'Unknown')}: {e}")
            continue
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(vcard_strings))
    
    logger.info(f"Successfully wrote {len(contacts)} contacts to {output_path}")


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
        if phone.get('type'):
            tel.type_param = phone['type']
    
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
    
    # Photo
    if contact.get('photo'):
        vcard.add('photo').value = contact['photo']
    
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

