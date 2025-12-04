"""
Intelligent contact merging module.
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger("contact_deduplication")


class ContactMerger:
    """
    Intelligently merges duplicate contacts while preserving all information.
    """
    
    def merge_contacts(self, duplicate_group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge a group of duplicate contacts into a single contact.
        
        Args:
            duplicate_group: List of contact dictionaries to merge
        
        Returns:
            Merged contact dictionary
        """
        if not duplicate_group:
            return {}
        
        if len(duplicate_group) == 1:
            return duplicate_group[0].copy()
        
        # Start with the first contact as base
        merged = duplicate_group[0].copy()
        
        # Remove normalization fields before merging (but keep raw_vcard_block)
        for key in list(merged.keys()):
            if key.startswith('_') and key != 'raw_vcard_block':
                del merged[key]
        
        # Merge remaining contacts
        for contact in duplicate_group[1:]:
            merged = self._merge_two_contacts(merged, contact)
        
        return merged
    
    def _merge_two_contacts(self, base: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two contacts, with base taking precedence where appropriate.
        
        Args:
            base: Base contact (takes precedence)
            other: Other contact to merge in
        
        Returns:
            Merged contact
        """
        merged = base.copy()
        
        # Remove normalization fields
        for key in list(merged.keys()):
            if key.startswith('_'):
                del merged[key]
        
        # Name: Use most complete name
        merged['name'] = self._merge_names(base, other)
        merged['first_name'] = self._merge_field(base.get('first_name'), other.get('first_name'), prefer_longer=True)
        merged['last_name'] = self._merge_field(base.get('last_name'), other.get('last_name'), prefer_longer=True)
        merged['middle_name'] = self._merge_field(base.get('middle_name'), other.get('middle_name'), prefer_longer=True)
        merged['prefix'] = self._merge_field(base.get('prefix'), other.get('prefix'))
        merged['suffix'] = self._merge_field(base.get('suffix'), other.get('suffix'))
        
        # Phone numbers: Merge all unique
        merged['phones'] = self._merge_phone_numbers(
            base.get('phones', []),
            other.get('phones', [])
        )
        
        # Email addresses: Merge all unique
        merged['emails'] = self._merge_email_addresses(
            base.get('emails', []),
            other.get('emails', [])
        )
        
        # Addresses: Keep all unique addresses
        merged['addresses'] = self._merge_addresses(
            base.get('addresses', []),
            other.get('addresses', [])
        )
        
        # URLs: Merge unique
        merged['urls'] = self._merge_lists(base.get('urls', []), other.get('urls', []))
        
        # Organization: Prefer more complete
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
        
        # Notes: Combine intelligently
        merged['notes'] = self._merge_notes(
            base.get('notes', []),
            other.get('notes', [])
        )
        
        # Dates: Keep all (birthday, anniversary)
        if not merged.get('birthday') and other.get('birthday'):
            merged['birthday'] = other['birthday']
        if not merged.get('anniversary') and other.get('anniversary'):
            merged['anniversary'] = other['anniversary']
        
        # Photo: Prefer base, but use other if base doesn't have one
        if not merged.get('photo') and other.get('photo'):
            merged['photo'] = other['photo']
        
        # Raw vCard block: CRITICAL for preserving binary data (photos, Base64)
        # Prefer the raw block with more data (likely has photos/binary)
        base_raw = merged.get('raw_vcard_block', '')
        other_raw = other.get('raw_vcard_block', '')
        
        if base_raw and other_raw:
            # Prefer the one with more data (likely has photos/binary)
            if len(other_raw) > len(base_raw):
                merged['raw_vcard_block'] = other_raw
                logger.debug(f"Using other contact's raw_vcard_block (longer, likely has more binary data)")
            # Otherwise keep base (already set)
        elif other_raw and not base_raw:
            # Use other's raw_vcard_block if base doesn't have one
            merged['raw_vcard_block'] = other_raw
            logger.debug(f"Using other contact's raw_vcard_block (base had none)")
        # If base has one and other doesn't, keep base (already set)
        
        # Custom fields: Merge all
        merged['custom_fields'] = self._merge_custom_fields(
            base.get('custom_fields', {}),
            other.get('custom_fields', {})
        )
        
        return merged
    
    def _merge_names(self, base: Dict[str, Any], other: Dict[str, Any]) -> str:
        """Merge names, preferring the most complete."""
        base_name = base.get('name', '').strip()
        other_name = other.get('name', '').strip()
        
        if not base_name:
            return other_name
        if not other_name:
            return base_name
        
        # Prefer longer name (more complete)
        if len(base_name) >= len(other_name):
            return base_name
        return other_name
    
    def _merge_field(self, base_value: Any, other_value: Any, prefer_longer: bool = False) -> Any:
        """Merge a simple field, preferring base value."""
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
    
    def _merge_phone_numbers(self, base_phones: List[Dict], other_phones: List[Dict]) -> List[Dict]:
        """
        Merge phone number lists, keeping unique phone+type combinations.
        
        Important: The same phone number with different types (e.g., CELL vs HOME)
        should be kept as separate entries since they represent different purposes.
        """
        merged = []
        seen_combinations = set()
        
        # Normalize phone numbers for comparison
        def normalize_phone(phone_dict):
            number = phone_dict.get('number', '')
            # Remove formatting for comparison
            return ''.join(filter(str.isdigit, number))
        
        def get_phone_key(phone_dict):
            """Create a unique key from phone number + type combination."""
            normalized = normalize_phone(phone_dict)
            phone_type = phone_dict.get('type', 'OTHER').upper()
            # Sort type values for consistent comparison (e.g., "CELL,VOICE" vs "VOICE,CELL")
            type_parts = sorted(phone_type.split(',')) if phone_type else ['OTHER']
            return (normalized, ','.join(type_parts))
        
        # Add base phones
        for phone in base_phones:
            key = get_phone_key(phone)
            if key[0] and key not in seen_combinations:  # key[0] is the normalized number
                merged.append(phone.copy())
                seen_combinations.add(key)
        
        # Add other phones that aren't duplicates (same number + same type)
        for phone in other_phones:
            key = get_phone_key(phone)
            if key[0] and key not in seen_combinations:
                merged.append(phone.copy())
                seen_combinations.add(key)
        
        return merged
    
    def _merge_email_addresses(self, base_emails: List[Dict], other_emails: List[Dict]) -> List[Dict]:
        """Merge email lists, keeping unique addresses."""
        merged = []
        seen_emails = set()
        
        # Add base emails
        for email in base_emails:
            addr = email.get('address', '').lower().strip()
            if addr and addr not in seen_emails:
                merged.append(email.copy())
                seen_emails.add(addr)
        
        # Add other emails that aren't duplicates
        for email in other_emails:
            addr = email.get('address', '').lower().strip()
            if addr and addr not in seen_emails:
                merged.append(email.copy())
                seen_emails.add(addr)
        
        return merged
    
    def _merge_addresses(self, base_addresses: List[Dict], other_addresses: List[Dict]) -> List[Dict]:
        """Merge address lists, keeping unique addresses."""
        merged = []
        seen_addresses = set()
        
        def address_key(addr):
            """Create a key for address comparison."""
            parts = [
                addr.get('street', '').lower().strip(),
                addr.get('city', '').lower().strip(),
                addr.get('postal_code', '').strip()
            ]
            return '|'.join(parts)
        
        # Add base addresses
        for addr in base_addresses:
            key = address_key(addr)
            if key and key not in seen_addresses:
                merged.append(addr.copy())
                seen_addresses.add(key)
        
        # Add other addresses that aren't duplicates
        for addr in other_addresses:
            key = address_key(addr)
            if key and key not in seen_addresses:
                merged.append(addr.copy())
                seen_addresses.add(key)
        
        return merged
    
    def _merge_notes(self, base_notes: List[str], other_notes: List[str]) -> List[str]:
        """Merge notes, avoiding exact duplicates."""
        merged = []
        seen_notes = set()
        
        for note in base_notes + other_notes:
            note_normalized = note.strip().lower()
            if note_normalized and note_normalized not in seen_notes:
                merged.append(note)
                seen_notes.add(note_normalized)
        
        return merged
    
    def _merge_lists(self, base_list: List, other_list: List) -> List:
        """Merge two lists, keeping unique items."""
        merged = []
        seen = set()
        
        for item in base_list + other_list:
            item_str = str(item).lower().strip()
            if item_str and item_str not in seen:
                merged.append(item)
                seen.add(item_str)
        
        return merged
    
    def _merge_custom_fields(self, base_fields: Dict, other_fields: Dict) -> Dict:
        """Merge custom fields from both contacts."""
        merged = base_fields.copy()
        
        for key, values in other_fields.items():
            if key not in merged:
                merged[key] = []
            
            # Add unique values
            # Handle both dict and simple value formats
            existing_values = set()
            for v in merged[key]:
                if isinstance(v, dict):
                    existing_values.add(str(v.get('value', v)).lower())
                else:
                    existing_values.add(str(v).lower())
            
            for value in values:
                if isinstance(value, dict):
                    value_str = str(value.get('value', value)).lower()
                else:
                    value_str = str(value).lower()
                
                if value_str not in existing_values:
                    merged[key].append(value)
                    existing_values.add(value_str)
        
        return merged

