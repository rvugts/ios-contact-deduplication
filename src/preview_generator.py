"""
Preview generation and display module.

This module provides functionality to generate and display previews of
duplicate detection and merging operations.

Dependencies:
    - typing: Standard library for type hints
    - logging: Standard library for logging
    - pathlib: Standard library for path handling
    - json: Standard library for JSON serialization
"""
# pylint: disable=logging-fstring-interpolation

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("contact_deduplication")


class PreviewGenerator:
    """
    Generates and displays previews of duplicate detection and merging.
    """

    def __init__(self) -> None:
        """Initialize the preview generator."""
        self.preview_data: Dict[str, Any] = {
            'duplicate_groups': [],
            'statistics': {}
        }

    def generate_preview(
        self,
        duplicate_groups: List[List[Dict[str, Any]]],
        total_contacts: int,
        merged_contacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate preview data for duplicate groups and merge results.

        :param duplicate_groups: List of duplicate groups
        :param total_contacts: Total number of contacts processed
        :param merged_contacts: List of merged contacts
        :return: Preview data dictionary
        """
        self.preview_data['duplicate_groups'] = []

        for group_id, group in enumerate(duplicate_groups, 1):
            group_info = {
                'id': group_id,
                'contacts': [],
                'merged_contact': None
            }

            for contact in group:
                contact_info = {
                    'name': contact.get('name', 'Unknown'),
                    'phones': [
                        p.get('number', '') for p in contact.get('phones', [])
                    ],
                    'emails': [
                        e.get('address', '') for e in contact.get('emails', [])
                    ]
                }
                group_info['contacts'].append(contact_info)

            self.preview_data['duplicate_groups'].append(group_info)

        total_duplicates = sum(len(group) for group in duplicate_groups)
        contacts_in_duplicates = total_duplicates
        final_count = len(merged_contacts)
        reduction = (
            (total_contacts - final_count) / total_contacts * 100
            if total_contacts > 0 else 0
        )

        self.preview_data['statistics'] = {
            'total_contacts': total_contacts,
            'duplicate_groups': len(duplicate_groups),
            'contacts_in_duplicates': contacts_in_duplicates,
            'contacts_merged': contacts_in_duplicates - len(duplicate_groups),
            'final_contacts': final_count,
            'reduction_percent': reduction
        }

        return self.preview_data

    def display_preview(
        self,
        preview_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Display preview in the console.

        :param preview_data: Preview data dictionary (uses self.preview_data
                             if None)
        """
        if preview_data is None:
            preview_data = self.preview_data

        stats = preview_data.get('statistics', {})
        groups = preview_data.get('duplicate_groups', [])

        print("\n" + "=" * 80)
        print("DUPLICATE DETECTION PREVIEW")
        print("=" * 80)
        print()

        print("STATISTICS:")
        print(f"  Total contacts processed: {stats.get('total_contacts', 0)}")
        print(
            f"  Duplicate groups found: {stats.get('duplicate_groups', 0)}"
        )
        print(
            f"  Contacts in duplicate groups: "
            f"{stats.get('contacts_in_duplicates', 0)}"
        )
        print(
            f"  Contacts to be merged: {stats.get('contacts_merged', 0)}"
        )
        print(f"  Final contact count: {stats.get('final_contacts', 0)}")
        print(f"  Reduction: {stats.get('reduction_percent', 0):.1f}%")
        print()

        max_groups_to_show = 10
        groups_to_show = groups[:max_groups_to_show]

        if groups_to_show:
            print(f"DUPLICATE GROUPS (showing first {len(groups_to_show)}):")
            print()

            for group in groups_to_show:
                print(
                    f"Group #{group['id']} ({len(group['contacts'])} "
                    f"duplicates):"
                )
                for i, contact in enumerate(group['contacts'], 1):
                    print(f"  {i}. {contact['name']}")
                    if contact.get('phones'):
                        phones = ', '.join(contact['phones'][:2])
                        print(f"     Phones: {phones}")
                    if contact.get('emails'):
                        emails = ', '.join(contact['emails'][:2])
                        print(f"     Emails: {emails}")
                print()

            if len(groups) > max_groups_to_show:
                remaining = len(groups) - max_groups_to_show
                print(f"... and {remaining} more groups")
                print()

        print("=" * 80)
        print()

    def save_preview_to_file(
        self,
        output_path: Path,
        preview_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save preview data to a JSON file.

        :param output_path: Path where preview should be saved
        :param preview_data: Preview data dictionary (uses self.preview_data
                             if None)
        """
        if preview_data is None:
            preview_data = self.preview_data

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(preview_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Preview saved to {output_path}")

    def _format_phone_list(
        self,
        phones: List[Dict[str, Any]],
        max_display: int = 3
    ) -> str:
        """
        Format phone list for display.

        :param phones: List of phone dictionaries
        :param max_display: Maximum number of phones to display
        :return: Formatted phone string
        """
        phone_str = ', '.join([
            p.get('number', '') for p in phones[:max_display]
        ])
        if len(phones) > max_display:
            phone_str += f" (+{len(phones) - max_display} more)"
        return phone_str

    def _format_email_list(
        self,
        emails: List[Dict[str, Any]],
        max_display: int = 3
    ) -> str:
        """
        Format email list for display.

        :param emails: List of email dictionaries
        :param max_display: Maximum number of emails to display
        :return: Formatted email string
        """
        email_str = ', '.join([
            e.get('address', '') for e in emails[:max_display]
        ])
        if len(emails) > max_display:
            email_str += f" (+{len(emails) - max_display} more)"
        return email_str

    def _display_merged_contact(
        self,
        group_id: int,
        merged: Dict[str, Any],
        group: List[Dict[str, Any]]
    ) -> None:
        """
        Display a single merged contact.

        :param group_id: Group ID
        :param merged: Merged contact dictionary
        :param group: Original duplicate group
        """
        print(f"Group #{group_id} → Merged Contact:")
        print(f"  Name: {merged.get('name', 'Unknown')}")

        phones = merged.get('phones', [])
        if phones:
            print(f"  Phones: {self._format_phone_list(phones)}")

        emails = merged.get('emails', [])
        if emails:
            print(f"  Emails: {self._format_email_list(emails)}")

        print(f"  Source contacts: {len(group)}")
        print()

    def display_merge_preview(
        self,
        duplicate_groups: List[List[Dict[str, Any]]],
        merged_contacts_map: Dict[int, Dict[str, Any]],
        show_all: bool = False
    ) -> bool:
        """
        Display preview of how contacts will be merged.

        :param duplicate_groups: List of duplicate groups
        :param merged_contacts_map: Dictionary mapping group ID to merged
                                    contact
        :param show_all: If True, show all groups; if False, show first 10
                         and ask
        :return: True if user wants to proceed, False otherwise
        """
        print("\n" + "=" * 80)
        print("MERGE PREVIEW")
        print("=" * 80)
        print()

        max_groups_to_show = 10
        groups_to_show = duplicate_groups if show_all else \
            duplicate_groups[:max_groups_to_show]

        for group_id, group in enumerate(groups_to_show, 1):
            merged = merged_contacts_map.get(group_id)
            if merged:
                self._display_merged_contact(group_id, merged, group)

        if not show_all and len(duplicate_groups) > max_groups_to_show:
            remaining = len(duplicate_groups) - max_groups_to_show
            print(f"... and {remaining} more groups")
            print()
            print("=" * 80)
            print()

            if sys.stdin.isatty():
                try:
                    response = input(
                        f"Show all {len(duplicate_groups)} merge previews? "
                        f"(yes/no): "
                    ).strip().lower()
                    if response in ['yes', 'y']:
                        self._display_all_merges(
                            duplicate_groups,
                            merged_contacts_map
                        )
                except (EOFError, KeyboardInterrupt):
                    pass

        return True

    def _display_all_merges(
        self,
        duplicate_groups: List[List[Dict[str, Any]]],
        merged_contacts_map: Dict[int, Dict[str, Any]]
    ) -> None:
        """
        Display all merge previews.

        :param duplicate_groups: List of duplicate groups
        :param merged_contacts_map: Dictionary mapping group ID to merged
                                    contact
        """
        print("\n" + "=" * 80)
        print("ALL MERGE PREVIEWS")
        print("=" * 80)
        print()

        for group_id, group in enumerate(duplicate_groups, 1):
            merged = merged_contacts_map.get(group_id)
            if merged:
                self._display_merged_contact(group_id, merged, group)

        print("=" * 80)
        print()
