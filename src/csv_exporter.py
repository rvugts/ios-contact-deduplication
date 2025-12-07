"""
CSV export module for contact data.

This module provides functionality to export contacts to CSV format for easy
viewing and import into spreadsheet applications.

Dependencies:
    - csv: Standard library for CSV file handling
    - pathlib: Standard library for path handling
    - typing: Standard library for type hints
    - logging: Standard library for logging
"""
# pylint: disable=logging-fstring-interpolation

import csv
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("contact_deduplication")

# Maximum number of phones, emails, and addresses to include in CSV
MAX_PHONES = 5
MAX_EMAILS = 5
MAX_ADDRESSES = 3


def _format_date(date_value: Any) -> str:
    """
    Format a date value for CSV export.

    :param date_value: Date value (string, date object, or None)
    :return: Formatted date string or empty string
    """
    if not date_value:
        return ''
    return str(date_value)


def _format_address(addr: Dict[str, Any]) -> str:
    """
    Format an address dictionary as a single string.

    :param addr: Address dictionary
    :return: Formatted address string
    """
    address_fields = ['street', 'city', 'region', 'postal_code', 'country']
    parts = [addr.get(field, '') for field in address_fields if addr.get(field)]
    return ', '.join(parts)


def _format_notes(notes: List[str]) -> str:
    """
    Format notes list as a single string.

    :param notes: List of note strings
    :return: Formatted notes string (semicolon-separated)
    """
    if not notes:
        return ''
    return '; '.join(str(note) for note in notes if note)


def _generate_column_names(
    prefix: str,
    max_count: int,
    type_suffix: str = 'Type',
    value_suffix: str = ''
) -> List[str]:
    """
    Generate column names for a repeating field type.

    :param prefix: Field prefix (e.g., 'Phone', 'Email', 'Address')
    :param max_count: Maximum number of fields to generate columns for
    :param type_suffix: Suffix for type column
    :param value_suffix: Suffix for value column
    :return: List of column names (type, value pairs)
    """
    columns = []
    for i in range(1, max_count + 1):
        columns.append(f'{prefix} {i} {type_suffix}')
        value_label = f'{prefix} {i} {value_suffix}'.strip()
        columns.append(value_label)
    return columns


def _get_phone_columns() -> List[str]:
    """
    Get list of phone column names.

    :return: List of column names for phones
    """
    return _generate_column_names('Phone', MAX_PHONES, value_suffix='Number')


def _get_email_columns() -> List[str]:
    """
    Get list of email column names.

    :return: List of column names for emails
    """
    return _generate_column_names('Email', MAX_EMAILS, value_suffix='Address')


def _get_address_columns() -> List[str]:
    """
    Get list of address column names.

    :return: List of column names for addresses
    """
    return _generate_column_names('Address', MAX_ADDRESSES, value_suffix='')


def _get_csv_headers() -> List[str]:
    """
    Get CSV header row.

    :return: List of column header names
    """
    base_headers = [
        'Name',
        'First Name',
        'Last Name',
        'Middle Name',
        'Prefix',
        'Suffix',
    ]
    extended_headers = [
        'Organization',
        'Title',
        'Department',
        'Notes',
        'Birthday',
        'Anniversary',
    ]

    headers = base_headers[:]
    headers.extend(_get_phone_columns())
    headers.extend(_get_email_columns())
    headers.extend(_get_address_columns())
    headers.extend(extended_headers)
    return headers


def _extract_field_values(
    items: List[Dict[str, Any]],
    max_count: int,
    type_key: str,
    value_key: str,
    formatter: Optional[Callable[[Dict[str, Any]], str]] = None
) -> List[str]:
    """
    Extract field values for CSV row from a list of dictionaries.

    :param items: List of field dictionaries
    :param max_count: Maximum number of fields to extract
    :param type_key: Key for type field in dictionary
    :param value_key: Key for value field in dictionary
    :param formatter: Optional formatter function for value
    :return: List of field values (type, value pairs)
    """
    values = []
    for i in range(max_count):
        if i < len(items):
            item = items[i]
            values.append(str(item.get(type_key, '')))
            value = item.get(value_key, '')
            if formatter:
                value = formatter(item)
            values.append(str(value))
        else:
            values.extend(['', ''])
    return values


def _get_phone_values(phones: List[Dict[str, Any]]) -> List[str]:
    """
    Extract phone values for CSV row.

    :param phones: List of phone dictionaries
    :return: List of phone values (type, number pairs)
    """
    return _extract_field_values(
        phones, MAX_PHONES, 'type', 'number'
    )


def _get_email_values(emails: List[Dict[str, Any]]) -> List[str]:
    """
    Extract email values for CSV row.

    :param emails: List of email dictionaries
    :return: List of email values (type, address pairs)
    """
    return _extract_field_values(
        emails, MAX_EMAILS, 'type', 'address'
    )


def _get_address_values(addresses: List[Dict[str, Any]]) -> List[str]:
    """
    Extract address values for CSV row.

    :param addresses: List of address dictionaries
    :return: List of address values (type, formatted address pairs)
    """
    return _extract_field_values(
        addresses, MAX_ADDRESSES, 'type', '', _format_address
    )


def _contact_to_csv_row(contact: Dict[str, Any]) -> List[str]:
    """
    Convert a contact dictionary to a CSV row.

    :param contact: Contact dictionary
    :return: List of CSV row values
    """
    row = [
        contact.get('name', ''),
        contact.get('first_name', ''),
        contact.get('last_name', ''),
        contact.get('middle_name', ''),
        contact.get('prefix', ''),
        contact.get('suffix', ''),
    ]

    # Add phone values
    row.extend(_get_phone_values(contact.get('phones', [])))

    # Add email values
    row.extend(_get_email_values(contact.get('emails', [])))

    # Add address values
    row.extend(_get_address_values(contact.get('addresses', [])))

    # Add remaining fields
    row.extend([
        contact.get('organization', ''),
        contact.get('title', ''),
        contact.get('department', ''),
        _format_notes(contact.get('notes', [])),
        _format_date(contact.get('birthday')),
        _format_date(contact.get('anniversary')),
    ])

    return row


def export_contacts_to_csv(
    contacts: List[Dict[str, Any]],
    output_path: Path,
    normalize_phones: bool = False
) -> None:
    """
    Export contacts to a CSV file.

    :param contacts: List of contact dictionaries
    :param output_path: Path where CSV file should be written
    :param normalize_phones: Whether phone numbers should be normalized
                             (should be done before calling this function)
    :raises IOError: If file cannot be written
    """
    if normalize_phones:
        logger.info(
            "Note: Phone normalization should be applied before CSV export. "
            "Proceeding with export..."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = _get_csv_headers()

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)

            # Write header row
            writer.writerow(headers)

            # Write contact rows
            rows = [_contact_to_csv_row(contact) for contact in contacts]
            writer.writerows(rows)

        logger.info(
            f"Successfully exported {len(contacts)} contacts to {output_path}"
        )

    except IOError as e:
        logger.error(f"Failed to write CSV file {output_path}: {e}")
        raise
