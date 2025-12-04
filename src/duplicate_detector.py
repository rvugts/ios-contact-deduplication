"""
Duplicate detection module with multi-strategy matching.

This module provides functionality to detect duplicate contacts using multiple
matching strategies including exact matching, fuzzy name matching, and
phone/email matching.

Dependencies:
    - phonenumbers: Third-party library for phone number parsing and
      normalization
    - rapidfuzz: Third-party library for fuzzy string matching
    - typing: Standard library for type hints
    - logging: Standard library for logging
"""
# pylint: disable=logging-fstring-interpolation

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import phonenumbers
from phonenumbers import NumberParseException
from rapidfuzz import fuzz

logger = logging.getLogger("contact_deduplication")


class DuplicateDetector:
    """
    Detects duplicate contacts using multiple matching strategies.
    """

    def __init__(self, fuzzy_threshold: int = 85):
        """
        Initialize the duplicate detector.

        :param fuzzy_threshold: Similarity threshold for fuzzy matching (0-100)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.phone_cache: Dict[str, Optional[str]] = {}
        self.email_cache: Dict[str, Optional[str]] = {}

    def find_duplicates(
        self,
        contacts: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Find all duplicate groups in the contact list.

        :param contacts: List of contact dictionaries
        :return: List of duplicate groups, where each group is a list of
                 contacts
        """
        logger.info(
            f"Starting duplicate detection for {len(contacts)} contacts..."
        )

        normalized_contacts = [
            self._normalize_contact(contact, i)
            for i, contact in enumerate(contacts)
        ]

        similarity_graph = self._build_similarity_graph(normalized_contacts)
        duplicate_groups = self._find_connected_components(
            normalized_contacts,
            similarity_graph
        )

        duplicate_groups = [
            group for group in duplicate_groups if len(group) > 1
        ]

        filtered_groups, ice_count = self._filter_ice_contacts(duplicate_groups)

        if ice_count > 0:
            logger.info(
                f"Excluded {ice_count} ICE contacts from merging "
                f"(intentional duplicates)"
            )

        logger.info(
            f"Found {len(filtered_groups)} duplicate groups "
            f"(excluding ICE contacts)"
        )
        return filtered_groups

    def _filter_ice_contacts(
        self,
        duplicate_groups: List[List[Dict[str, Any]]]
    ) -> Tuple[List[List[Dict[str, Any]]], int]:
        """
        Filter out groups that contain ICE contacts.

        :param duplicate_groups: List of duplicate groups
        :return: Tuple of (filtered groups, count of excluded ICE contacts)
        """
        filtered_groups = []
        ice_contacts_count = 0

        for group in duplicate_groups:
            has_ice = any(contact.get('_is_ice', False) for contact in group)
            if not has_ice:
                filtered_groups.append(group)
            else:
                ice_contacts_count += len(group)
                contact_names = [
                    c.get('name', 'Unknown') for c in group
                ]
                logger.info(
                    f"Skipping merge for ICE contact group: {contact_names}"
                )

        return filtered_groups, ice_contacts_count

    def _is_ice_contact(self, contact: Dict[str, Any]) -> bool:
        """
        Check if a contact is an ICE (In Case of Emergency) contact.

        :param contact: Contact dictionary
        :return: True if contact is an ICE contact
        """
        name = contact.get('name', '').upper()
        first_name = contact.get('first_name', '').upper()
        last_name = contact.get('last_name', '').upper()

        return 'ICE' in name or 'ICE' in first_name or 'ICE' in last_name

    def _normalize_contact(
        self,
        contact: Dict[str, Any],
        index: int
    ) -> Dict[str, Any]:
        """
        Normalize contact data for comparison.

        :param contact: Original contact dictionary
        :param index: Contact index for reference
        :return: Contact dictionary with normalized fields
        """
        normalized = contact.copy()
        normalized['_index'] = index
        normalized['_is_ice'] = self._is_ice_contact(contact)

        normalized['_normalized_name'] = self._normalize_name(
            contact.get('name', '')
        )
        normalized['_normalized_first'] = self._normalize_name(
            contact.get('first_name', '')
        )
        normalized['_normalized_last'] = self._normalize_name(
            contact.get('last_name', '')
        )

        normalized['_normalized_phones'] = [
            self._normalize_phone(phone['number'])
            for phone in contact.get('phones', [])
            if self._normalize_phone(phone['number'])
        ]

        normalized['_normalized_emails'] = [
            self._normalize_email(email['address'])
            for email in contact.get('emails', [])
            if self._normalize_email(email['address'])
        ]

        return normalized

    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name for comparison.

        :param name: Original name string
        :return: Normalized name (lowercase, trimmed, extra spaces removed)
        """
        if not name:
            return ''
        return ' '.join(name.lower().split())

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """
        Normalize a phone number for comparison.

        :param phone: Original phone number string
        :return: Normalized phone number in E.164 format, or None if invalid
        """
        if not phone:
            return None

        if phone in self.phone_cache:
            return self.phone_cache[phone]

        cleaned = ''.join(filter(str.isdigit, phone))
        if not cleaned:
            self.phone_cache[phone] = None
            return None

        normalized = self._parse_phone_number(phone, cleaned)
        self.phone_cache[phone] = normalized
        return normalized

    def _parse_phone_number(self, phone: str, cleaned: str) -> Optional[str]:
        """
        Parse and normalize phone number using phonenumbers library.

        :param phone: Original phone string
        :param cleaned: Cleaned digits-only phone string
        :return: Normalized phone number or None
        """
        try:
            parsed = phonenumbers.parse(phone, "US")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed,
                    phonenumbers.PhoneNumberFormat.E164
                )
        except NumberParseException:
            pass

        try:
            if cleaned.startswith('+'):
                parsed = phonenumbers.parse(phone, None)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(
                        parsed,
                        phonenumbers.PhoneNumberFormat.E164
                    )
        except NumberParseException:
            pass

        if len(cleaned) >= 10:
            if not cleaned.startswith('+'):
                if len(cleaned) == 10:
                    return f"+1{cleaned}"
                return f"+{cleaned}"
            return cleaned

        return None

    def _normalize_email(self, email: str) -> Optional[str]:
        """
        Normalize an email address for comparison.

        :param email: Original email string
        :return: Normalized email (lowercase, trimmed), or None if invalid
        """
        if not email:
            return None

        if email in self.email_cache:
            return self.email_cache[email]

        normalized = email.lower().strip()
        if '@' in normalized and '.' in normalized.split('@')[1]:
            self.email_cache[email] = normalized
            return normalized

        self.email_cache[email] = None
        return None

    def _build_similarity_graph(
        self,
        contacts: List[Dict[str, Any]]
    ) -> Dict[int, Set[int]]:
        """
        Build a graph of similar contacts.

        :param contacts: List of normalized contacts
        :return: Dictionary mapping contact index to set of similar contact
                 indices
        """
        graph = {i: set() for i in range(len(contacts))}

        for i, _ in enumerate(contacts):
            for j in range(i + 1, len(contacts)):
                if self._are_duplicates(contacts[i], contacts[j]):
                    graph[i].add(j)
                    graph[j].add(i)

        return graph

    def _are_duplicates(
        self,
        contact1: Dict[str, Any],
        contact2: Dict[str, Any]
    ) -> bool:
        """
        Check if two contacts are duplicates.

        :param contact1: First normalized contact
        :param contact2: Second normalized contact
        :return: True if contacts are duplicates
        """
        if contact1.get('_is_ice', False) or contact2.get('_is_ice', False):
            return False

        if self._has_exact_phone_match(contact1, contact2):
            return True

        if self._has_exact_email_match(contact1, contact2):
            return True

        if self._has_exact_name_match(contact1, contact2):
            return True

        if self._has_fuzzy_name_match(contact1, contact2):
            return True

        if self._has_phone_email_with_similar_name(contact1, contact2):
            return True

        return False

    def _has_exact_phone_match(
        self,
        contact1: Dict[str, Any],
        contact2: Dict[str, Any]
    ) -> bool:
        """
        Check if contacts have matching phone numbers.

        :param contact1: First contact
        :param contact2: Second contact
        :return: True if phones match
        """
        phones1 = set(contact1.get('_normalized_phones', []))
        phones2 = set(contact2.get('_normalized_phones', []))
        return bool(phones1 and phones2 and phones1.intersection(phones2))

    def _has_exact_email_match(
        self,
        contact1: Dict[str, Any],
        contact2: Dict[str, Any]
    ) -> bool:
        """
        Check if contacts have matching email addresses.

        :param contact1: First contact
        :param contact2: Second contact
        :return: True if emails match
        """
        emails1 = set(contact1.get('_normalized_emails', []))
        emails2 = set(contact2.get('_normalized_emails', []))
        return bool(emails1 and emails2 and emails1.intersection(emails2))

    def _has_exact_name_match(
        self,
        contact1: Dict[str, Any],
        contact2: Dict[str, Any]
    ) -> bool:
        """
        Check if contacts have exact name matches.

        :param contact1: First contact
        :param contact2: Second contact
        :return: True if names match exactly
        """
        name1 = contact1.get('_normalized_name', '')
        name2 = contact2.get('_normalized_name', '')

        if name1 and name2 and name1 == name2:
            return True

        first1 = contact1.get('_normalized_first', '')
        last1 = contact1.get('_normalized_last', '')
        first2 = contact2.get('_normalized_first', '')
        last2 = contact2.get('_normalized_last', '')

        return bool(
            first1 and last1 and first2 and last2 and
            first1 == first2 and last1 == last2
        )

    def _has_fuzzy_name_match(
        self,
        contact1: Dict[str, Any],
        contact2: Dict[str, Any]
    ) -> bool:
        """
        Check if contacts have fuzzy name matches.

        :param contact1: First contact
        :param contact2: Second contact
        :return: True if names match with fuzzy similarity
        """
        name1 = contact1.get('_normalized_name', '')
        name2 = contact2.get('_normalized_name', '')

        if name1 and name2:
            similarity = fuzz.ratio(name1, name2)
            if similarity >= self.fuzzy_threshold:
                return True

        first1 = contact1.get('_normalized_first', '')
        last1 = contact1.get('_normalized_last', '')
        first2 = contact2.get('_normalized_first', '')
        last2 = contact2.get('_normalized_last', '')

        if first1 and last1 and first2 and last2:
            full1 = f"{first1} {last1}".strip()
            full2 = f"{first2} {last2}".strip()
            if full1 and full2:
                similarity = fuzz.ratio(full1, full2)
                if similarity >= self.fuzzy_threshold:
                    return True

        return False

    def _has_phone_email_with_similar_name(
        self,
        contact1: Dict[str, Any],
        contact2: Dict[str, Any]
    ) -> bool:
        """
        Check if contacts have phone/email match with similar name.

        :param contact1: First contact
        :param contact2: Second contact
        :return: True if phone/email matches with similar name
        """
        phones1 = set(contact1.get('_normalized_phones', []))
        phones2 = set(contact2.get('_normalized_phones', []))
        has_phone_match = bool(phones1 and phones2 and phones1.intersection(phones2))

        emails1 = set(contact1.get('_normalized_emails', []))
        emails2 = set(contact2.get('_normalized_emails', []))
        has_email_match = bool(emails1 and emails2 and emails1.intersection(emails2))

        name1 = contact1.get('_normalized_name', '')
        name2 = contact2.get('_normalized_name', '')

        if (has_phone_match or has_email_match) and name1 and name2:
            similarity = fuzz.ratio(name1, name2)
            if similarity >= 70:
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

        :param contacts: List of normalized contacts
        :param graph: Similarity graph
        :return: List of duplicate groups
        """
        visited = set()
        groups = []

        def dfs(node: int, group: List[int]) -> None:
            """Depth-first search to find connected component."""
            visited.add(node)
            group.append(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, group)

        for i, _ in enumerate(contacts):
            if i not in visited:
                group_indices = []
                dfs(i, group_indices)
                group_contacts = [contacts[idx] for idx in group_indices]
                groups.append(group_contacts)

        return groups

    def get_match_criteria(
        self,
        contact1: Dict[str, Any],
        contact2: Dict[str, Any]
    ) -> str:
        """
        Determine the matching criteria used to identify duplicates.

        :param contact1: First contact
        :param contact2: Second contact
        :return: Description of match criteria
        """
        criteria = []

        phones1 = set(contact1.get('_normalized_phones', []))
        phones2 = set(contact2.get('_normalized_phones', []))
        if phones1 and phones2 and phones1.intersection(phones2):
            criteria.append("Phone number")

        emails1 = set(contact1.get('_normalized_emails', []))
        emails2 = set(contact2.get('_normalized_emails', []))
        if emails1 and emails2 and emails1.intersection(emails2):
            criteria.append("Email address")

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
