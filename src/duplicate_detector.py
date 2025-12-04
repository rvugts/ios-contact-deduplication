"""
Duplicate detection module with multi-strategy matching.
"""

import phonenumbers
from phonenumbers import NumberParseException
from rapidfuzz import fuzz
from typing import List, Dict, Any, Set, Tuple, Optional
import logging

logger = logging.getLogger("contact_deduplication")


class DuplicateDetector:
    """
    Detects duplicate contacts using multiple matching strategies.
    """
    
    def __init__(self, fuzzy_threshold: int = 85):
        """
        Initialize the duplicate detector.
        
        Args:
            fuzzy_threshold: Similarity threshold for fuzzy matching (0-100)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.phone_cache = {}  # Cache normalized phone numbers
        self.email_cache = {}  # Cache normalized emails
    
    def find_duplicates(self, contacts: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Find all duplicate groups in the contact list.
        
        Args:
            contacts: List of contact dictionaries
        
        Returns:
            List of duplicate groups, where each group is a list of contacts
        """
        logger.info(f"Starting duplicate detection for {len(contacts)} contacts...")
        
        # Normalize all contacts
        normalized_contacts = []
        for i, contact in enumerate(contacts):
            normalized = self._normalize_contact(contact, i)
            normalized_contacts.append(normalized)
        
        # Build similarity graph
        similarity_graph = self._build_similarity_graph(normalized_contacts)
        
        # Find connected components (duplicate groups)
        duplicate_groups = self._find_connected_components(normalized_contacts, similarity_graph)
        
        # Filter out single-contact groups (no duplicates)
        duplicate_groups = [group for group in duplicate_groups if len(group) > 1]
        
        # Filter out groups that contain ICE contacts (they should not be merged)
        filtered_groups = []
        ice_contacts_count = 0
        for group in duplicate_groups:
            has_ice = any(contact.get('_is_ice', False) for contact in group)
            if not has_ice:
                filtered_groups.append(group)
            else:
                ice_contacts_count += len(group)
                logger.info(f"Skipping merge for ICE contact group: {[c.get('name', 'Unknown') for c in group]}")
        
        if ice_contacts_count > 0:
            logger.info(f"Excluded {ice_contacts_count} ICE contacts from merging (intentional duplicates)")
        
        logger.info(f"Found {len(filtered_groups)} duplicate groups (excluding ICE contacts)")
        return filtered_groups
    
    def _is_ice_contact(self, contact: Dict[str, Any]) -> bool:
        """
        Check if a contact is an ICE (In Case of Emergency) contact.
        
        Args:
            contact: Contact dictionary
        
        Returns:
            True if contact is an ICE contact
        """
        name = contact.get('name', '').upper()
        first_name = contact.get('first_name', '').upper()
        last_name = contact.get('last_name', '').upper()
        
        # Check if "ICE" appears in any name field
        return 'ICE' in name or 'ICE' in first_name or 'ICE' in last_name
    
    def _normalize_contact(self, contact: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Normalize contact data for comparison.
        
        Args:
            contact: Original contact dictionary
            index: Contact index for reference
        
        Returns:
            Contact dictionary with normalized fields
        """
        normalized = contact.copy()
        normalized['_index'] = index
        normalized['_is_ice'] = self._is_ice_contact(contact)
        
        # Normalize name
        normalized['_normalized_name'] = self._normalize_name(contact.get('name', ''))
        normalized['_normalized_first'] = self._normalize_name(contact.get('first_name', ''))
        normalized['_normalized_last'] = self._normalize_name(contact.get('last_name', ''))
        
        # Normalize phone numbers
        normalized['_normalized_phones'] = []
        for phone in contact.get('phones', []):
            normalized_phone = self._normalize_phone(phone['number'])
            if normalized_phone:
                normalized['_normalized_phones'].append(normalized_phone)
        
        # Normalize email addresses
        normalized['_normalized_emails'] = []
        for email in contact.get('emails', []):
            normalized_email = self._normalize_email(email['address'])
            if normalized_email:
                normalized['_normalized_emails'].append(normalized_email)
        
        return normalized
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name for comparison.
        
        Args:
            name: Original name string
        
        Returns:
            Normalized name (lowercase, trimmed, extra spaces removed)
        """
        if not name:
            return ''
        return ' '.join(name.lower().split())
    
    def _normalize_phone(self, phone: str) -> Optional[str]:
        """
        Normalize a phone number for comparison.
        
        Args:
            phone: Original phone number string
        
        Returns:
            Normalized phone number in E.164 format, or None if invalid
        """
        if not phone:
            return None
        
        # Remove common formatting
        cleaned = ''.join(filter(str.isdigit, phone))
        if not cleaned:
            return None
        
        # Try to parse and normalize
        try:
            # Try parsing with default region (US)
            parsed = phonenumbers.parse(phone, "US")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            pass
        
        # If parsing fails, try with international format
        try:
            if cleaned.startswith('+'):
                parsed = phonenumbers.parse(phone, None)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            pass
        
        # Fallback: return cleaned digits with + prefix if it looks international
        if len(cleaned) >= 10:
            if not cleaned.startswith('+'):
                # Assume US number if 10 digits, otherwise add +
                if len(cleaned) == 10:
                    return f"+1{cleaned}"
                else:
                    return f"+{cleaned}"
            return cleaned
        
        return None
    
    def _normalize_email(self, email: str) -> Optional[str]:
        """
        Normalize an email address for comparison.
        
        Args:
            email: Original email string
        
        Returns:
            Normalized email (lowercase, trimmed), or None if invalid
        """
        if not email:
            return None
        normalized = email.lower().strip()
        # Basic email validation
        if '@' in normalized and '.' in normalized.split('@')[1]:
            return normalized
        return None
    
    def _build_similarity_graph(self, contacts: List[Dict[str, Any]]) -> Dict[int, Set[int]]:
        """
        Build a graph of similar contacts.
        
        Args:
            contacts: List of normalized contacts
        
        Returns:
            Dictionary mapping contact index to set of similar contact indices
        """
        graph = {i: set() for i in range(len(contacts))}
        
        # Compare all pairs
        for i in range(len(contacts)):
            for j in range(i + 1, len(contacts)):
                if self._are_duplicates(contacts[i], contacts[j]):
                    graph[i].add(j)
                    graph[j].add(i)
        
        return graph
    
    def _are_duplicates(self, contact1: Dict[str, Any], contact2: Dict[str, Any]) -> bool:
        """
        Check if two contacts are duplicates.
        
        Args:
            contact1: First normalized contact
            contact2: Second normalized contact
        
        Returns:
            True if contacts are duplicates
        """
        # Don't merge ICE contacts - they are intentional
        if contact1.get('_is_ice', False) or contact2.get('_is_ice', False):
            return False
        
        # Exact phone match
        phones1 = set(contact1.get('_normalized_phones', []))
        phones2 = set(contact2.get('_normalized_phones', []))
        if phones1 and phones2 and phones1.intersection(phones2):
            return True
        
        # Exact email match
        emails1 = set(contact1.get('_normalized_emails', []))
        emails2 = set(contact2.get('_normalized_emails', []))
        if emails1 and emails2 and emails1.intersection(emails2):
            return True
        
        # Exact name match
        name1 = contact1.get('_normalized_name', '')
        name2 = contact2.get('_normalized_name', '')
        if name1 and name2 and name1 == name2:
            return True
        
        # Exact first + last name match
        first1 = contact1.get('_normalized_first', '')
        last1 = contact1.get('_normalized_last', '')
        first2 = contact2.get('_normalized_first', '')
        last2 = contact2.get('_normalized_last', '')
        
        if first1 and last1 and first2 and last2:
            if first1 == first2 and last1 == last2:
                return True
        
        # Fuzzy name matching
        if name1 and name2:
            similarity = fuzz.ratio(name1, name2)
            if similarity >= self.fuzzy_threshold:
                return True
        
        # Fuzzy first + last name matching
        if first1 and last1 and first2 and last2:
            full1 = f"{first1} {last1}".strip()
            full2 = f"{first2} {last2}".strip()
            if full1 and full2:
                similarity = fuzz.ratio(full1, full2)
                if similarity >= self.fuzzy_threshold:
                    return True
        
        # Phone or email match with similar name
        has_phone_match = bool(phones1 and phones2 and phones1.intersection(phones2))
        has_email_match = bool(emails1 and emails2 and emails1.intersection(emails2))
        
        if (has_phone_match or has_email_match) and name1 and name2:
            similarity = fuzz.ratio(name1, name2)
            if similarity >= 70:  # Lower threshold when phone/email matches
                return True
        
        return False
    
    def _find_connected_components(
        self, 
        contacts: List[Dict[str, Any]], 
        graph: Dict[int, Set[int]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Find connected components in the similarity graph.
        Uses DFS to find all contacts in the same duplicate group.
        
        Args:
            contacts: List of normalized contacts
            graph: Similarity graph
        
        Returns:
            List of duplicate groups
        """
        visited = set()
        groups = []
        
        def dfs(node: int, group: List[int]):
            """Depth-first search to find connected component."""
            visited.add(node)
            group.append(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, group)
        
        for i in range(len(contacts)):
            if i not in visited:
                group_indices = []
                dfs(i, group_indices)
                # Convert indices to actual contacts
                group_contacts = [contacts[idx] for idx in group_indices]
                groups.append(group_contacts)
        
        return groups
    
    def get_match_criteria(self, contact1: Dict[str, Any], contact2: Dict[str, Any]) -> str:
        """
        Determine the matching criteria used to identify duplicates.
        
        Args:
            contact1: First contact
            contact2: Second contact
        
        Returns:
            Description of match criteria
        """
        criteria = []
        
        # Check phone match
        phones1 = set(contact1.get('_normalized_phones', []))
        phones2 = set(contact2.get('_normalized_phones', []))
        if phones1 and phones2 and phones1.intersection(phones2):
            criteria.append("Phone number")
        
        # Check email match
        emails1 = set(contact1.get('_normalized_emails', []))
        emails2 = set(contact2.get('_normalized_emails', []))
        if emails1 and emails2 and emails1.intersection(emails2):
            criteria.append("Email address")
        
        # Check name match
        name1 = contact1.get('_normalized_name', '')
        name2 = contact2.get('_normalized_name', '')
        if name1 and name2:
            if name1 == name2:
                criteria.append("Exact name")
            else:
                similarity = fuzz.ratio(name1, name2)
                if similarity >= self.fuzzy_threshold:
                    criteria.append(f"Fuzzy name ({similarity}% similar)")
        
        return ", ".join(criteria) if criteria else "Multiple criteria"

