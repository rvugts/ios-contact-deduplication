"""
Intelligent contact merging module.

This module provides functionality to merge duplicate contacts while preserving
all information from each contact, including phone types, addresses, and
custom fields.

Dependencies:
    - typing: Standard library for type hints
    - logging: Standard library for logging
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger("contact_deduplication")


class ContactMerger: # pylint: disable=too-few-public-methods
    """
    Intelligently merges duplicate contacts while preserving all information.
    """

    def merge_contacts(
        self,
        duplicate_group: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge a group of duplicate contacts into a single contact.

        :param duplicate_group: List of contact dictionaries to merge
        :return: Merged contact dictionary
        """
        if not duplicate_group:
            return {}

        if len(duplicate_group) == 1:
            return duplicate_group[0].copy()

        merged = duplicate_group[0].copy()

        for key in list(merged.keys()):
            if key.startswith('_') and key != 'raw_vcard_block':
                del merged[key]

        for contact in duplicate_group[1:]:
            merged = self._merge_two_contacts(merged, contact)

        return merged

    def _merge_two_contacts(
        self,
        base: Dict[str, Any],
        other: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two contacts, with base taking precedence where appropriate.

        :param base: Base contact (takes precedence)
        :param other: Other contact to merge in
        :return: Merged contact
        """
        merged = base.copy()

        for key in list(merged.keys()):
            if key.startswith('_'):
                del merged[key]

        merged['name'] = self._merge_names(base, other)
        merged['first_name'] = self._merge_field(
            base.get('first_name'),
            other.get('first_name'),
            prefer_longer=True
        )
        merged['last_name'] = self._merge_field(
            base.get('last_name'),
            other.get('last_name'),
            prefer_longer=True
        )
        merged['middle_name'] = self._merge_field(
            base.get('middle_name'),
            other.get('middle_name'),
            prefer_longer=True
        )
        merged['prefix'] = self._merge_field(
            base.get('prefix'),
            other.get('prefix')
        )
        merged['suffix'] = self._merge_field(
            base.get('suffix'),
            other.get('suffix')
        )

        merged['phones'] = self._merge_phone_numbers(
            base.get('phones', []),
            other.get('phones', [])
        )

        merged['emails'] = self._merge_email_addresses(
            base.get('emails', []),
            other.get('emails', [])
        )

        merged['addresses'] = self._merge_addresses(
            base.get('addresses', []),
            other.get('addresses', [])
        )

        merged['urls'] = self._merge_lists(
            base.get('urls', []),
            other.get('urls', [])
        )

        merged['organization'] = self._merge_field(
            base.get('organization'),
            other.get('organization'),
            prefer_longer=True
        )
        merged['title'] = self._merge_field(
            base.get('title'),
            other.get('title'),
            prefer_longer=True
        )
        merged['department'] = self._merge_field(
            base.get('department'),
            other.get('department'),
            prefer_longer=True
        )

        merged['notes'] = self._merge_notes(
            base.get('notes', []),
            other.get('notes', [])
        )

        if not merged.get('birthday') and other.get('birthday'):
            merged['birthday'] = other['birthday']
        if not merged.get('anniversary') and other.get('anniversary'):
            merged['anniversary'] = other['anniversary']

        if not merged.get('photo') and other.get('photo'):
            merged['photo'] = other['photo']

        merged['raw_vcard_block'] = self._merge_raw_blocks(
            merged.get('raw_vcard_block', ''),
            other.get('raw_vcard_block', '')
        )

        merged['custom_fields'] = self._merge_custom_fields(
            base.get('custom_fields', {}),
            other.get('custom_fields', {})
        )

        return merged

    def _merge_names(
        self,
        base: Dict[str, Any],
        other: Dict[str, Any]
    ) -> str:
        """
        Merge names, preferring the most complete.

        :param base: Base contact dictionary
        :param other: Other contact dictionary
        :return: Merged name string
        """
        base_name = base.get('name', '').strip()
        other_name = other.get('name', '').strip()

        if not base_name:
            return other_name
        if not other_name:
            return base_name

        if len(base_name) >= len(other_name):
            return base_name
        return other_name

    def _merge_field(
        self,
        base_value: Any,
        other_value: Any,
        prefer_longer: bool = False
    ) -> Any:
        """
        Merge a simple field, preferring base value.

        :param base_value: Base field value
        :param other_value: Other field value
        :param prefer_longer: If True, prefer longer value
        :return: Merged field value
        """
        if not base_value:
            return other_value
        if not other_value:
            return base_value

        if prefer_longer:
            base_str = str(base_value).strip()
            other_str = str(other_value).strip()
            if len(other_str) > len(base_str):
                return other_value

        return base_value

    def _merge_raw_blocks(
        self,
        base_raw: str,
        other_raw: str
    ) -> str:
        """
        Merge raw vCard blocks, preferring the one with more data.

        :param base_raw: Base raw vCard block
        :param other_raw: Other raw vCard block
        :return: Selected raw vCard block
        """
        if base_raw and other_raw:
            if len(other_raw) > len(base_raw):
                logger.debug(
                    "Using other contact's raw_vcard_block (longer, likely "
                    "has more binary data)"
                )
                return other_raw
            return base_raw

        if other_raw and not base_raw:
            logger.debug("Using other contact's raw_vcard_block (base had none)")
            return other_raw

        return base_raw

    def _normalize_phone(self, phone_dict: Dict[str, Any]) -> str:
        """
        Normalize phone number for comparison.

        :param phone_dict: Phone dictionary with 'number' key
        :return: Normalized phone number (digits only)
        """
        number = phone_dict.get('number', '')
        return ''.join(filter(str.isdigit, number))

    def _get_phone_key(self, phone_dict: Dict[str, Any]) -> tuple:
        """
        Create a unique key from phone number + type combination.

        :param phone_dict: Phone dictionary
        :return: Tuple of (normalized_number, normalized_type)
        """
        normalized = self._normalize_phone(phone_dict)
        phone_type = phone_dict.get('type', 'OTHER').upper()
        type_parts = sorted(phone_type.split(',')) if phone_type else \
            ['OTHER']
        return (normalized, ','.join(type_parts))

    def _merge_phone_numbers(
        self,
        base_phones: List[Dict[str, Any]],
        other_phones: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge phone number lists, keeping unique phone+type combinations.

        Important: The same phone number with different types (e.g., CELL vs
        HOME) should be kept as separate entries since they represent
        different purposes.

        :param base_phones: List of phone dictionaries from base contact
        :param other_phones: List of phone dictionaries from other contact
        :return: Merged list of unique phone dictionaries
        """
        merged = []
        seen_combinations = set()

        for phone in base_phones:
            key = self._get_phone_key(phone)
            if key[0] and key not in seen_combinations:
                merged.append(phone.copy())
                seen_combinations.add(key)

        for phone in other_phones:
            key = self._get_phone_key(phone)
            if key[0] and key not in seen_combinations:
                merged.append(phone.copy())
                seen_combinations.add(key)

        return merged

    def _merge_email_addresses(
        self,
        base_emails: List[Dict[str, Any]],
        other_emails: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge email lists, keeping unique addresses.

        :param base_emails: List of email dictionaries from base contact
        :param other_emails: List of email dictionaries from other contact
        :return: Merged list of unique email dictionaries
        """
        merged = []
        seen_emails = set()

        for email in base_emails:
            addr = email.get('address', '').lower().strip()
            if addr and addr not in seen_emails:
                merged.append(email.copy())
                seen_emails.add(addr)

        for email in other_emails:
            addr = email.get('address', '').lower().strip()
            if addr and addr not in seen_emails:
                merged.append(email.copy())
                seen_emails.add(addr)

        return merged

    def _address_key(self, addr: Dict[str, Any]) -> str:
        """
        Create a key for address comparison.

        :param addr: Address dictionary
        :return: Address key string
        """
        parts = [
            addr.get('street', '').lower().strip(),
            addr.get('city', '').lower().strip(),
            addr.get('postal_code', '').strip()
        ]
        return '|'.join(parts)

    def _merge_addresses(
        self,
        base_addresses: List[Dict[str, Any]],
        other_addresses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge address lists, keeping unique addresses.

        :param base_addresses: List of address dictionaries from base contact
        :param other_addresses: List of address dictionaries from other contact
        :return: Merged list of unique address dictionaries
        """
        merged = []
        seen_addresses = set()

        for addr in base_addresses:
            key = self._address_key(addr)
            if key and key not in seen_addresses:
                merged.append(addr.copy())
                seen_addresses.add(key)

        for addr in other_addresses:
            key = self._address_key(addr)
            if key and key not in seen_addresses:
                merged.append(addr.copy())
                seen_addresses.add(key)

        return merged

    def _merge_notes(
        self,
        base_notes: List[str],
        other_notes: List[str]
    ) -> List[str]:
        """
        Merge notes, avoiding exact duplicates.

        :param base_notes: List of note strings from base contact
        :param other_notes: List of note strings from other contact
        :return: Merged list of unique notes
        """
        merged = []
        seen_notes = set()

        for note in base_notes + other_notes:
            note_normalized = note.strip().lower()
            if note_normalized and note_normalized not in seen_notes:
                merged.append(note)
                seen_notes.add(note_normalized)

        return merged

    def _merge_lists(
        self,
        base_list: List[Any],
        other_list: List[Any]
    ) -> List[Any]:
        """
        Merge two lists, keeping unique items.

        :param base_list: Base list
        :param other_list: Other list
        :return: Merged list with unique items
        """
        merged = []
        seen = set()

        for item in base_list + other_list:
            item_str = str(item).lower().strip()
            if item_str and item_str not in seen:
                merged.append(item)
                seen.add(item_str)

        return merged

    def _get_field_value(self, value: Any) -> str:
        """
        Extract string value from field data (handles dict and simple values).

        :param value: Field value (dict or simple value)
        :return: String representation of value
        """
        if isinstance(value, dict):
            return str(value.get('value', value)).lower()
        return str(value).lower()

    def _merge_custom_fields(
        self,
        base_fields: Dict[str, List[Any]],
        other_fields: Dict[str, List[Any]]
    ) -> Dict[str, List[Any]]:
        """
        Merge custom fields from both contacts.

        :param base_fields: Custom fields dictionary from base contact
        :param other_fields: Custom fields dictionary from other contact
        :return: Merged custom fields dictionary
        """
        merged = base_fields.copy()

        for key, values in other_fields.items():
            if key not in merged:
                merged[key] = []

            existing_values = {
                self._get_field_value(v) for v in merged[key]
            }

            for value in values:
                value_str = self._get_field_value(value)
                if value_str not in existing_values:
                    merged[key].append(value)
                    existing_values.add(value_str)

        return merged
