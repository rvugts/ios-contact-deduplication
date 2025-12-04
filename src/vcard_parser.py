"""
vCard file parsing module for reading and writing vCard format contacts.

This module handles parsing vCard (.vcf) files, extracting contact information,
and writing contacts back to vCard format. It preserves binary data such as
photos and handles various vCard encoding formats.

Dependencies:
    - vobject: Third-party library for parsing vCard objects (>=0.9.6)
    - pathlib: Standard library for path handling
    - typing: Standard library for type hints
    - logging: Standard library for logging
"""
# pylint: disable=logging-fstring-interpolation, too-many-lines, broad-except

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import vobject

logger = logging.getLogger("contact_deduplication")

# Constants
DEFAULT_PHONE_TYPE = 'OTHER'
DEFAULT_EMAIL_TYPE = 'OTHER'
DEFAULT_ADDRESS_TYPE = 'OTHER'
STANDARD_VCARD_FIELDS = {
    'n', 'fn', 'tel', 'email', 'adr', 'url', 'org', 'title',
    'note', 'bday', 'anniversary', 'photo', 'version', 'prodid'
}
MAX_CONTACT_NAME_PARTS = 5


def _normalize_line_endings(content: str) -> str:
    """Normalize line endings to Unix format."""
    return content.replace('\r\n', '\n')


def _is_vcard_begin(line: str) -> bool:
    """Check if line is a vCard BEGIN marker."""
    return 'BEGIN:VCARD' in line.strip().upper()


def _is_vcard_end(line: str) -> bool:
    """Check if line is a vCard END marker."""
    return 'END:VCARD' in line.strip().upper()


def _split_vcard_blocks(content: str) -> List[str]:
    """
    Split vCard content into individual vCard blocks.

    :param content: Full vCard file content
    :return: List of individual vCard block strings
    """
    blocks = []
    current_block = []
    in_block = False

    lines = _normalize_line_endings(content).split('\n')

    for line in lines:
        if _is_vcard_begin(line):
            if in_block and current_block:
                blocks.append('\n'.join(current_block))
            current_block = [line]
            in_block = True
        elif in_block:
            current_block.append(line)
            if _is_vcard_end(line):
                blocks.append('\n'.join(current_block))
                current_block = []
                in_block = False

    if in_block and current_block:
        blocks.append('\n'.join(current_block))

    return blocks

def _create_empty_contact() -> Dict[str, Any]:
    """Create an empty contact dictionary with default structure."""
    return {
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
        'custom_fields': {}
    }


def _create_minimal_contact(block: str, block_num: int) -> Dict[str, Any]:
    """
    Create a minimal contact dictionary from a raw vCard block.

    :param block: Raw vCard block string
    :param block_num: Block number for identification
    :return: Minimal contact dictionary
    """
    contact = _create_empty_contact()
    contact['name'] = f'Contact {block_num}'
    contact['raw_vcard_block'] = block
    return contact

def _ensure_raw_block(contact: Dict[str, Any], block: str) -> None:
    """Ensure contact has raw_vcard_block set."""
    if not contact.get('raw_vcard_block'):
        contact['raw_vcard_block'] = block

def _read_file_content(file_path: Path) -> str:
    """
    Read vCard file content with proper encoding handling.

    :param file_path: Path to the vCard file
    :return: File content as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()

def _try_parse_vcard_with_vobject(
    block: str,
    block_num: int
) -> Optional[Dict[str, Any]]:
    """Attempt to parse vCard block using vobject library."""
    try:
        vcards = list(vobject.readComponents(block))
        for vcard in vcards:
            try:
                contact = _parse_single_vcard(
                    vcard, raw_block=block, block_num=block_num
                )
                if contact:
                    _ensure_raw_block(contact, block)
                    return contact
            except Exception as error:
                logger.debug(
                    f"Error parsing vCard entry in block {block_num}: {error}"
                )
                continue
    except Exception as error:
        logger.debug(
            f"vobject parsing failed for block {block_num}: {error}"
        )
    return None


def _parse_vcard_block(
    block: str,
    block_num: int
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Parse a single vCard block using vobject library.

    :param block: Raw vCard block string
    :param block_num: Block number for logging
    :return: Tuple of (contact dict or None, success boolean)
    """
    contact = _try_parse_vcard_with_vobject(block, block_num)

    if not contact:
        logger.debug(
            f"vobject failed for block {block_num}, trying manual extraction"
        )
        contact = _parse_vcard_manually(block, block_num)

    if contact:
        _ensure_raw_block(contact, block)
        return contact, True

    return None, False

def _has_vcard_markers(block: str) -> bool:
    """Check if block has BEGIN and END vCard markers."""
    block_upper = block.upper()
    return 'BEGIN:VCARD' in block_upper and 'END:VCARD' in block_upper


def _process_failed_block(
    block: str,
    block_num: int,
    contacts: List[Dict[str, Any]]
) -> bool:
    """Process a failed vCard block, creating minimal contact if valid."""
    if _has_vcard_markers(block):
        minimal = _create_minimal_contact(block, block_num)
        contacts.append(minimal)
        logger.debug(
            f"Created minimal contact from block {block_num} using raw block"
        )
        return True

    logger.warning(f"Block {block_num} missing BEGIN/END markers. Skipping.")
    return False


def parse_vcard_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parse a vCard file and extract all contacts.

    :param file_path: Path to the .vcf file
    :return: List of contact dictionaries with normalized field names
    :raises FileNotFoundError: If the file doesn't exist
    :raises ValueError: If the file is malformed or empty
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    try:
        content = _read_file_content(file_path)
        vcard_blocks = _split_vcard_blocks(content)
        logger.info(f"Split file into {len(vcard_blocks)} vCard blocks")

        contacts = []
        failed_count = 0

        for block_num, block in enumerate(vcard_blocks, 1):
            contact, success = _parse_vcard_block(block, block_num)

            if success and contact:
                contacts.append(contact)
            else:
                if not _process_failed_block(block, block_num, contacts):
                    failed_count += 1

        if failed_count > 0:
            logger.warning(
                f"Failed to parse {failed_count} out of "
                f"{len(vcard_blocks)} vCard blocks"
            )

        if not contacts:
            raise ValueError(f"No valid contacts found in {file_path}")

        logger.info(
            f"Successfully parsed {len(contacts)} contacts from {file_path}"
        )
        return contacts

    except Exception as error:
        logger.error(f"Error reading vCard file {file_path}: {error}")
        raise

def _is_continuation_line(line: str) -> bool:
    """Check if line is a continuation (folded) line."""
    return line.startswith(' ') or line.startswith('\t')


def _extract_fn_from_block(vcard_block: str) -> Optional[str]:
    """
    Extract FN (formatted name) field from raw vCard block.

    :param vcard_block: Raw vCard block string
    :return: Formatted name or None
    """
    lines = vcard_block.split('\n')
    current_fn = None

    for line in lines:
        line_upper = line.strip().upper()

        if line_upper.startswith('FN:'):
            current_fn = line.split(':', 1)[1] if ':' in line else ''
        elif current_fn is not None and _is_continuation_line(line):
            current_fn += line.lstrip()
        elif current_fn is not None:
            return current_fn.strip()

    return current_fn.strip() if current_fn else None

def _is_placeholder_name(name: str) -> bool:
    """Check if name is a placeholder."""
    return not name or name.startswith('Contact ')


def _get_name_status(original_name: str, current_name: str) -> str:
    """Get descriptive status of the contact name."""
    if not original_name:
        return 'empty'
    if original_name.startswith('Contact '):
        return f'placeholder ({original_name})'
    if not current_name:
        return 'missing'
    if current_name.startswith('Contact '):
        return f'placeholder ({current_name})'
    return f'invalid ({current_name})'


def _try_extract_name_from_fn(
    contact: Dict[str, Any],
    block_num: int,
    raw_block: str,
    original_name: str
) -> bool:
    """Try to extract name from FN field in raw vCard block."""
    fn_name = _extract_fn_from_block(raw_block)
    if not fn_name:
        return False

    contact['name'] = fn_name
    status = 'empty' if not original_name else f'placeholder ({original_name})'
    logger.warning(
        f"Contact {block_num}: Name was {status}, "
        f"extracted from vCard FN field: {contact['name']}"
    )
    return True


def _try_use_organization_as_name(
    contact: Dict[str, Any],
    block_num: int,
    original_name: str
) -> bool:
    """Try to use organization as contact name."""
    if not contact.get('organization'):
        return False

    contact['name'] = contact['organization']
    status = _get_name_status(original_name, original_name)
    logger.warning(
        f"Contact {block_num}: Name was {status}, "
        f"using organization name: {contact['name']}"
    )
    return True


def _assign_placeholder_name(
    contact: Dict[str, Any],
    block_num: int,
    original_name: str
) -> None:
    """Assign a placeholder name to contact."""
    new_name = f'Contact {block_num}'
    status = _get_name_status(original_name, contact['name'])
    logger.warning(
        f"Contact {block_num}: Name was {status}, "
        f"assigned placeholder: {new_name}"
    )
    contact['name'] = new_name


def _update_contact_name(
    contact: Dict[str, Any],
    block_num: int,
    raw_block: str
) -> None:
    """
    Update contact name from raw vCard block if missing or placeholder.

    :param contact: Contact dictionary to update
    :param block_num: Block number for logging
    :param raw_block: Raw vCard block string
    """
    original_name = contact.get('name', '')

    if not _is_placeholder_name(original_name):
        return

    if _is_placeholder_name(contact.get('name', '')):
        if _try_extract_name_from_fn(
            contact, block_num, raw_block, original_name
        ):
            return

        if _try_use_organization_as_name(contact, block_num, original_name):
            return

        _assign_placeholder_name(contact, block_num, original_name)

def _process_name_field(contact: Dict[str, Any], value: str) -> None:
    """Process N (name) field from vCard."""
    parts = value.split(';')
    name_fields = ['last_name', 'first_name', 'middle_name', 'prefix', 'suffix']
    for i, field in enumerate(name_fields):
        if i < len(parts):
            contact[field] = parts[i]


def _process_org_field(contact: Dict[str, Any], value: str) -> None:
    """Process ORG (organization) field from vCard."""
    parts = value.split(';')
    if len(parts) >= 1:
        contact['organization'] = parts[0]
    if len(parts) >= 2:
        contact['department'] = parts[1]


def _process_custom_field(
    contact: Dict[str, Any],
    field_name: str,
    value: str
) -> None:
    """Process custom/extended vCard field."""
    if field_name not in contact['custom_fields']:
        contact['custom_fields'][field_name] = []

    serialized = f"{field_name}:{value}"
    contact['custom_fields'][field_name].append({
        'value': value,
        'serialized': serialized
    })


def _process_manual_field(
    contact: Dict[str, Any],
    field_name: str,
    value: str
) -> None:
    """
    Process a manually extracted vCard field.

    :param contact: Contact dictionary to update
    :param field_name: Field name (e.g., 'FN', 'TEL', 'EMAIL')
    :param value: Field value
    """
    field_handlers = {
        'FN': lambda: contact.update({'name': value}),
        'N': lambda: _process_name_field(contact, value),
        'TEL': lambda: contact['phones'].append(
            {'number': value, 'type': DEFAULT_PHONE_TYPE}
        ),
        'EMAIL': lambda: contact['emails'].append(
            {'address': value, 'type': DEFAULT_EMAIL_TYPE}
        ),
        'ORG': lambda: _process_org_field(contact, value),
        'TITLE': lambda: contact.update({'title': value}),
        'NOTE': lambda: contact['notes'].append(value),
        'BDAY': lambda: contact.update({'birthday': value}),
        'ANNIVERSARY': lambda: contact.update({'anniversary': value}),
        'PHOTO': lambda: contact.update({'photo': value}),
    }

    handler = field_handlers.get(field_name)
    if handler:
        handler()
    elif field_name.startswith('X-') or field_name.startswith('ITEM'):
        _process_custom_field(contact, field_name, value)

def _should_skip_field(field_name: str) -> bool:
    """Check if field should be skipped during manual parsing."""
    return field_name in ['VERSION', 'PRODID', 'BEGIN', 'END']


def _finalize_current_field(
    contact: Dict[str, Any],
    current_field: Optional[str],
    current_value_parts: List[str]
) -> None:
    """Finalize and process accumulated field value."""
    if current_field and current_value_parts:
        full_value = ''.join(current_value_parts)
        if full_value:
            _process_manual_field(contact, current_field, full_value)


def _parse_vcard_manually(
    vcard_block: str,
    block_num: int
) -> Optional[Dict[str, Any]]:
    """
    Manually parse a vCard block when vobject fails.

    :param vcard_block: Raw vCard block string
    :param block_num: Block number for logging
    :return: Contact dictionary with basic fields or None if invalid
    """
    contact = _create_minimal_contact(vcard_block, block_num)
    lines = _normalize_line_endings(vcard_block).split('\n')
    current_field = None
    current_value_parts = []

    for line in lines:
        if _is_continuation_line(line):
            if current_field and current_value_parts:
                current_value_parts.append(line.lstrip())
            continue

        _finalize_current_field(contact, current_field, current_value_parts)
        current_field = None
        current_value_parts = []

        if not line.strip() or ':' not in line:
            continue

        parts = line.split(':', 1)
        if len(parts) == 2:
            field_part = parts[0].strip()
            value_part = parts[1]
            field_name = field_part.split(';')[0].upper()

            if not _should_skip_field(field_name):
                current_field = field_name
                current_value_parts = [value_part]

    _finalize_current_field(contact, current_field, current_value_parts)
    _update_contact_name(contact, block_num, vcard_block)

    return contact

def _build_name_from_parts(contact: Dict[str, Any]) -> str:
    """Build full name from contact name parts."""
    name_parts = [
        contact.get('prefix', ''),
        contact.get('first_name', ''),
        contact.get('middle_name', ''),
        contact.get('last_name', ''),
        contact.get('suffix', '')
    ]
    return ' '.join(filter(None, name_parts)).strip()

def _parse_phone_types(tel: Any) -> List[str]:
    """Extract phone types from vobject tel object."""
    if not (hasattr(tel, 'params') and tel.params):
        return []

    type_params = tel.params.get('TYPE', [])
    if isinstance(type_params, list):
        return [str(t).upper() for t in type_params]
    if type_params:
        return [str(type_params).upper()]
    return []

def _get_address_type(adr: Any) -> str:
    """Extract address type from vobject adr object."""
    if hasattr(adr, 'type_param_list') and adr.type_param_list:
        return ','.join(adr.type_param_list)
    return DEFAULT_ADDRESS_TYPE


def _safe_get_address_part(addr_parts: Any, index: int) -> str:
    """Safely extract address part at given index."""
    if isinstance(addr_parts, (list, tuple)) and len(addr_parts) > index:
        return str(addr_parts[index]) if addr_parts[index] else ''
    return ''


def _parse_address(adr: Any) -> Dict[str, Any]:
    """Parse address from vobject adr object."""
    addr_parts = adr.value
    return {
        'type': _get_address_type(adr),
        'street': _safe_get_address_part(addr_parts, 2),
        'city': _safe_get_address_part(addr_parts, 3),
        'region': _safe_get_address_part(addr_parts, 4),
        'postal_code': _safe_get_address_part(addr_parts, 5),
        'country': _safe_get_address_part(addr_parts, 6)
    }

def _parse_custom_field(item: Any) -> Dict[str, Any]:
    """Parse custom field from vobject item."""
    field_data = {'value': item.value, 'params': {}}

    if hasattr(item, 'params'):
        field_data['params'] = dict(item.params)

    try:
        field_data['serialized'] = item.serialize()
    except Exception:
        pass

    return field_data

def _parse_vcard_name(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse name fields from vCard."""
    if hasattr(vcard, 'n'):
        name_parts = vcard.n.value
        contact['last_name'] = name_parts.family or ''
        contact['first_name'] = name_parts.given or ''
        contact['middle_name'] = name_parts.additional or ''
        contact['prefix'] = name_parts.prefix or ''
        contact['suffix'] = name_parts.suffix or ''
        contact['name'] = _build_name_from_parts(contact)

    if hasattr(vcard, 'fn') and not contact['name']:
        contact['name'] = vcard.fn.value


def _parse_vcard_phones(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse phone numbers from vCard."""
    if not hasattr(vcard, 'tel_list'):
        return

    for tel in vcard.tel_list:
        types = _parse_phone_types(tel)
        phone_info = {
            'number': tel.value,
            'type': ','.join(types) if types else DEFAULT_PHONE_TYPE
        }
        contact['phones'].append(phone_info)


def _parse_vcard_emails(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse email addresses from vCard."""
    if not hasattr(vcard, 'email_list'):
        return

    for email in vcard.email_list:
        type_list = (email.type_param_list
                     if hasattr(email, 'type_param_list') else [])
        email_info = {
            'address': email.value,
            'type': ','.join(type_list) if type_list else DEFAULT_EMAIL_TYPE
        }
        contact['emails'].append(email_info)


def _parse_vcard_addresses(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse addresses from vCard."""
    if hasattr(vcard, 'adr_list'):
        contact['addresses'] = [_parse_address(adr) for adr in vcard.adr_list]


def _parse_vcard_urls(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse URLs from vCard."""
    if hasattr(vcard, 'url_list'):
        contact['urls'] = [url.value for url in vcard.url_list]


def _parse_vcard_organization(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse organization fields from vCard."""
    if not hasattr(vcard, 'org'):
        return

    org_parts = vcard.org.value
    if isinstance(org_parts, list) and len(org_parts) > 0:
        contact['organization'] = org_parts[0]
        if len(org_parts) > 1:
            contact['department'] = org_parts[1]


def _parse_vcard_notes(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse notes from vCard."""
    if hasattr(vcard, 'note_list'):
        contact['notes'] = [note.value for note in vcard.note_list]


def _parse_vcard_dates(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse date fields from vCard."""
    if hasattr(vcard, 'bday'):
        contact['birthday'] = vcard.bday.value
    if hasattr(vcard, 'anniversary'):
        contact['anniversary'] = vcard.anniversary.value


def _parse_vcard_custom_fields(vcard: Any, contact: Dict[str, Any]) -> None:
    """Parse custom fields from vCard."""
    for key in vcard.contents:
        if key not in STANDARD_VCARD_FIELDS:
            if key not in contact['custom_fields']:
                contact['custom_fields'][key] = []
            for item in vcard.contents[key]:
                field_data = _parse_custom_field(item)
                contact['custom_fields'][key].append(field_data)


def _finalize_contact_name_from_raw(
    contact: Dict[str, Any],
    raw_block: Optional[str]
) -> None:
    """Finalize contact name using raw block if name is missing."""
    if not _is_placeholder_name(contact.get('name', '')):
        return

    if raw_block:
        fn_name = _extract_fn_from_block(raw_block)
        if fn_name:
            contact['name'] = fn_name
            return

    if contact.get('organization'):
        contact['name'] = contact['organization']
        return

    if contact.get('first_name') or contact.get('last_name'):
        generated_name = _build_name_from_parts(contact)
        if generated_name:
            contact['name'] = generated_name


def _parse_single_vcard(
    vcard: vobject.base.Component,
    raw_block: Optional[str] = None,
    block_num: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse a single vCard object into a contact dictionary.

    :param vcard: vobject vCard component
    :param raw_block: Optional raw vCard block string (preserves binary data)
    :param block_num: Optional block number for logging
    :return: Contact dictionary or None if invalid
    """
    contact = _create_empty_contact()
    contact['raw_vcard'] = vcard

    if raw_block:
        contact['raw_vcard_block'] = raw_block

    _parse_vcard_name(vcard, contact)
    _parse_vcard_phones(vcard, contact)
    _parse_vcard_emails(vcard, contact)
    _parse_vcard_addresses(vcard, contact)
    _parse_vcard_urls(vcard, contact)
    _parse_vcard_organization(vcard, contact)

    if hasattr(vcard, 'title'):
        contact['title'] = vcard.title.value

    if hasattr(vcard, 'photo'):
        contact['photo'] = vcard.photo.value

    _parse_vcard_notes(vcard, contact)
    _parse_vcard_dates(vcard, contact)
    _parse_vcard_custom_fields(vcard, contact)

    if raw_block and block_num is not None:
        _update_contact_name(contact, block_num, raw_block)
    else:
        _finalize_contact_name_from_raw(contact, raw_block)

    return contact

def _should_keep_line(line: str) -> bool:
    """Check if line should be kept during vCard cleaning."""
    return bool(line.strip()) or _is_continuation_line(line)


def _clean_vcard_block(block: str) -> str:
    """Remove blank lines from vCard block while preserving line folding."""
    lines = block.split('\n')
    cleaned_lines = [line for line in lines if _should_keep_line(line)]
    return '\n'.join(cleaned_lines).rstrip('\n\r')

def _get_contact_name(contact: Dict[str, Any]) -> str:
    """Get contact name or default."""
    return contact.get('name', 'Unknown')


def _write_vcard_from_serialization(
    contact: Dict[str, Any],
    vcard_strings: List[str]
) -> None:
    """Write vCard using serialization fallback."""
    try:
        vcard = _contact_to_vcard(contact)
        serialized = vcard.serialize()
        cleaned_block = _clean_vcard_block(serialized)
        vcard_strings.append(cleaned_block)
    except Exception as error:
        logger.error(
            f"Failed to serialize contact "
            f"{_get_contact_name(contact)}: {error}"
        )


def _write_vcard_from_raw_block(
    contact: Dict[str, Any],
    vcard_strings: List[str]
) -> None:
    """Write vCard from raw block if available."""
    if contact.get('raw_vcard_block'):
        cleaned_block = _clean_vcard_block(contact['raw_vcard_block'])
        vcard_strings.append(cleaned_block)
        return

    logger.warning(
        f"Contact {_get_contact_name(contact)} missing raw_vcard_block, "
        f"using serialization fallback"
    )
    _write_vcard_from_serialization(contact, vcard_strings)

def _write_contact_with_fallback(
    contact: Dict[str, Any],
    vcard_strings: List[str]
) -> None:
    """Write contact with fallback to raw block if primary method fails."""
    try:
        _write_vcard_from_raw_block(contact, vcard_strings)
    except Exception as error:
        logger.error(
            f"Unexpected error processing contact "
            f"{_get_contact_name(contact)}: {error}"
        )
        if contact.get('raw_vcard_block'):
            try:
                cleaned_block = _clean_vcard_block(
                    contact['raw_vcard_block']
                )
                vcard_strings.append(cleaned_block)
            except Exception:
                logger.error(
                    f"Could not write raw_vcard_block for "
                    f"{_get_contact_name(contact)}, contact will be lost"
                )


def write_vcard_file(
    contacts: List[Dict[str, Any]],
    output_path: Path
) -> None:
    """
    Write contacts to a vCard file.

    :param contacts: List of contact dictionaries
    :param output_path: Path where the vCard file should be written
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vcard_strings = []
    for contact in contacts:
        _write_contact_with_fallback(contact, vcard_strings)

    with open(output_path, 'w', encoding='utf-8') as file:
        file.write('\n\n'.join(vcard_strings))
        if vcard_strings:
            file.write('\n')

    logger.info(
        f"Successfully wrote {len(contacts)} contacts to {output_path}"
    )

def _create_validation_report(
    expected_contact_count: int,
    input_contact_count: int,
    duplicate_groups_count: int
) -> Dict[str, Any]:
    """Create initial validation report structure."""
    return {
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


def _validate_contact_count(
    output_contacts: List[Dict[str, Any]],
    expected_count: int,
    report: Dict[str, Any]
) -> None:
    """Validate contact count matches expectations."""
    actual_count = len(output_contacts)
    if actual_count != expected_count:
        report['errors'].append(
            f"Contact count mismatch: expected {expected_count}, "
            f"got {actual_count}"
        )
        report['contacts_lost'] = expected_count - actual_count
    else:
        logger.info(f"Validation: Contact count matches expected ({expected_count})")


def _has_proper_name(contact: Dict[str, Any]) -> bool:
    """Check if contact has a proper (non-placeholder) name."""
    name = contact.get('name', '')
    return bool(name and not name.startswith('Contact '))


def _has_any_data(contact: Dict[str, Any]) -> bool:
    """Check if contact has any meaningful data."""
    return bool(
        _has_proper_name(contact) or
        contact.get('phones') or
        contact.get('emails') or
        contact.get('organization')
    )


def _validate_contact_data(
    output_contacts: List[Dict[str, Any]],
    report: Dict[str, Any]
) -> None:
    """Validate contact data quality."""
    contacts_without_name = []
    contacts_without_data = []

    for i, contact in enumerate(output_contacts, 1):
        if not _has_proper_name(contact):
            contacts_without_name.append(i)

        if not _has_any_data(contact):
            contacts_without_data.append(i)

    if contacts_without_name:
        report['warnings'].append(
            f"Found {len(contacts_without_name)} contacts without proper "
            f"names (indices: {contacts_without_name[:10]})"
        )

    if contacts_without_data:
        report['errors'].append(
            f"Found {len(contacts_without_data)} contacts without any data "
            f"(indices: {contacts_without_data[:10]})"
        )


def _calculate_phone_type_preservation(
    output_contacts: List[Dict[str, Any]],
    report: Dict[str, Any]
) -> None:
    """Calculate phone type preservation statistics."""
    total_phones = 0
    phones_with_types = 0

    for contact in output_contacts:
        for phone in contact.get('phones', []):
            total_phones += 1
            if phone.get('type') and phone['type'] != DEFAULT_PHONE_TYPE:
                phones_with_types += 1

    if total_phones > 0:
        preservation_percent = (phones_with_types / total_phones) * 100
        report['phone_types'] = {
            'total_phones': total_phones,
            'phones_with_types': phones_with_types,
            'preservation_percent': preservation_percent
        }
        logger.info(
            f"Phone type preservation: {phones_with_types}/{total_phones} "
            f"phones have types ({preservation_percent:.1f}%)"
        )


def _find_blank_lines_in_vcards(content: str) -> List[int]:
    """Find blank lines within vCard blocks."""
    lines = content.split('\n')
    blank_lines = []
    in_vcard = False

    for i, line in enumerate(lines, 1):
        line_upper = line.strip().upper()
        if line_upper == 'BEGIN:VCARD':
            in_vcard = True
        elif line_upper == 'END:VCARD':
            in_vcard = False
        elif in_vcard and not line.strip() and not _is_continuation_line(line):
            blank_lines.append(i)

    return blank_lines


def _validate_vcard_format(output_path: Path, report: Dict[str, Any]) -> None:
    """Validate vCard file format."""
    with open(output_path, 'r', encoding='utf-8') as file:
        content = file.read()

    blank_lines = _find_blank_lines_in_vcards(content)
    if blank_lines:
        report['errors'].append(
            f"Found {len(blank_lines)} blank lines within vCard blocks "
            f"(lines: {blank_lines[:10]})"
        )


def validate_vcard_file(
    output_path: Path,
    expected_contact_count: int,
    input_contact_count: int,
    duplicate_groups_count: int
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate the output vCard file to ensure no data was lost.

    :param output_path: Path to the output vCard file
    :param expected_contact_count: Expected number of contacts in output
    :param input_contact_count: Original number of contacts in input
    :param duplicate_groups_count: Number of duplicate groups merged
    :return: Tuple of (is_valid, validation_report_dict)
    """
    report = _create_validation_report(
        expected_contact_count, input_contact_count, duplicate_groups_count
    )

    if not output_path.exists():
        report['errors'].append(f"Output file does not exist: {output_path}")
        return False, report

    try:
        output_contacts = parse_vcard_file(output_path)
        report['parse_successful'] = True
        report['output_contact_count'] = len(output_contacts)

        _validate_contact_count(output_contacts, expected_contact_count, report)
        _validate_contact_data(output_contacts, report)
        _calculate_phone_type_preservation(output_contacts, report)
        _validate_vcard_format(output_path, report)

        report['valid'] = (
            len(report['errors']) == 0 and report['parse_successful']
        )

        if report['valid']:
            logger.info(
                "Validation passed: Output file is valid and all contacts "
                "are present"
            )
        else:
            logger.warning(
                f"Validation failed: {len(report['errors'])} errors found"
            )

        return report['valid'], report

    except Exception as error:
        report['errors'].append(f"Failed to parse output file: {error}")
        logger.error(f"Validation error: {error}")
        return False, report

def _build_phone_type_list(phone_type: Any) -> List[str]:
    """Build list of phone types from various formats."""
    if isinstance(phone_type, str):
        return [t.strip().upper() for t in phone_type.split(',') if t.strip()]
    if isinstance(phone_type, list):
        return [str(t).upper() for t in phone_type if t]
    return [str(phone_type).upper()]

def _add_name_to_vcard(vcard: Any, contact: Dict[str, Any]) -> None:
    """Add name fields to vCard."""
    if contact.get('first_name') or contact.get('last_name'):
        name_field = vcard.add('n')
        name_field.value = vobject.vcard.Name(
            family=contact.get('last_name', ''),
            given=contact.get('first_name', ''),
            additional=contact.get('middle_name', ''),
            prefix=contact.get('prefix', ''),
            suffix=contact.get('suffix', '')
        )


def _add_formatted_name_to_vcard(vcard: Any, contact: Dict[str, Any]) -> None:
    """Add formatted name (FN) to vCard."""
    if contact.get('name'):
        vcard.add('fn').value = contact['name']
    elif contact.get('first_name') or contact.get('last_name'):
        generated_name = _build_name_from_parts(contact)
        vcard.add('fn').value = generated_name if generated_name else 'Unknown'
    else:
        vcard.add('fn').value = 'Unknown'


def _add_phones_to_vcard(vcard: Any, contact: Dict[str, Any]) -> None:
    """Add phone numbers to vCard."""
    for phone in contact.get('phones', []):
        tel = vcard.add('tel')
        tel.value = phone['number']
        if phone.get('type') and phone['type'] != DEFAULT_PHONE_TYPE:
            types = _build_phone_type_list(phone['type'])
            if types:
                tel.params['TYPE'] = types


def _add_emails_to_vcard(vcard: Any, contact: Dict[str, Any]) -> None:
    """Add email addresses to vCard."""
    for email in contact.get('emails', []):
        email_obj = vcard.add('email')
        email_obj.value = email['address']
        if email.get('type'):
            email_obj.type_param = email['type']


def _add_addresses_to_vcard(vcard: Any, contact: Dict[str, Any]) -> None:
    """Add addresses to vCard."""
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


def _add_organization_to_vcard(vcard: Any, contact: Dict[str, Any]) -> None:
    """Add organization to vCard."""
    if not contact.get('organization'):
        return

    org = vcard.add('org')
    org_parts = [contact['organization']]
    if contact.get('department'):
        org_parts.append(contact['department'])
    org.value = org_parts


def _add_custom_fields_to_vcard(vcard: Any, contact: Dict[str, Any]) -> None:
    """Add custom fields to vCard."""
    for field_name, field_values in contact.get('custom_fields', {}).items():
        for field_data in field_values:
            if isinstance(field_data, dict):
                field_obj = vcard.add(field_name)
                field_obj.value = field_data['value']
                if field_data.get('params'):
                    for param_key, param_value in field_data['params'].items():
                        setattr(field_obj, param_key, param_value)
            else:
                vcard.add(field_name).value = field_data


def _contact_to_vcard(contact: Dict[str, Any]) -> vobject.base.Component:
    """Convert a contact dictionary to a vCard object."""
    vcard = vobject.vCard()

    _add_name_to_vcard(vcard, contact)
    _add_formatted_name_to_vcard(vcard, contact)
    _add_phones_to_vcard(vcard, contact)
    _add_emails_to_vcard(vcard, contact)
    _add_addresses_to_vcard(vcard, contact)

    for url in contact.get('urls', []):
        vcard.add('url').value = url

    _add_organization_to_vcard(vcard, contact)

    if contact.get('title'):
        vcard.add('title').value = contact['title']

    for note in contact.get('notes', []):
        vcard.add('note').value = note

    if contact.get('birthday'):
        vcard.add('bday').value = contact['birthday']

    if contact.get('anniversary'):
        vcard.add('anniversary').value = contact['anniversary']

    if contact.get('photo'):
        try:
            vcard.add('photo').value = contact['photo']
        except Exception:
            pass

    _add_custom_fields_to_vcard(vcard, contact)

    return vcard
