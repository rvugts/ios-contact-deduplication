"""
Preview generation and display module.
"""

from typing import List, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger("contact_deduplication")


class PreviewGenerator:
    """
    Generates and displays previews of duplicate detection and merging.
    """
    
    def __init__(self):
        """Initialize the preview generator."""
        self.preview_data = {
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
        
        Args:
            duplicate_groups: List of duplicate groups
            total_contacts: Total number of contacts processed
            merged_contacts: List of merged contacts
        
        Returns:
            Preview data dictionary
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
                    'phones': [p.get('number', '') for p in contact.get('phones', [])],
                    'emails': [e.get('address', '') for e in contact.get('emails', [])]
                }
                group_info['contacts'].append(contact_info)
            
            self.preview_data['duplicate_groups'].append(group_info)
        
        # Calculate statistics
        total_duplicates = sum(len(group) for group in duplicate_groups)
        contacts_in_duplicates = total_duplicates
        final_count = len(merged_contacts)
        reduction = ((total_contacts - final_count) / total_contacts * 100) if total_contacts > 0 else 0
        
        self.preview_data['statistics'] = {
            'total_contacts': total_contacts,
            'duplicate_groups': len(duplicate_groups),
            'contacts_in_duplicates': contacts_in_duplicates,
            'contacts_merged': contacts_in_duplicates - len(duplicate_groups),
            'final_contacts': final_count,
            'reduction_percent': reduction
        }
        
        return self.preview_data
    
    def display_preview(self, preview_data: Dict[str, Any] = None) -> None:
        """
        Display preview in the console.
        
        Args:
            preview_data: Preview data dictionary (uses self.preview_data if None)
        """
        if preview_data is None:
            preview_data = self.preview_data
        
        stats = preview_data.get('statistics', {})
        groups = preview_data.get('duplicate_groups', [])
        
        print("\n" + "=" * 80)
        print("DUPLICATE DETECTION PREVIEW")
        print("=" * 80)
        print()
        
        # Statistics
        print("STATISTICS:")
        print(f"  Total contacts processed: {stats.get('total_contacts', 0)}")
        print(f"  Duplicate groups found: {stats.get('duplicate_groups', 0)}")
        print(f"  Contacts in duplicate groups: {stats.get('contacts_in_duplicates', 0)}")
        print(f"  Contacts to be merged: {stats.get('contacts_merged', 0)}")
        print(f"  Final contact count: {stats.get('final_contacts', 0)}")
        print(f"  Reduction: {stats.get('reduction_percent', 0):.1f}%")
        print()
        
        # Duplicate groups (show first 10, or all if fewer)
        max_groups_to_show = 10
        groups_to_show = groups[:max_groups_to_show]
        
        if groups_to_show:
            print("DUPLICATE GROUPS (showing first {}):".format(len(groups_to_show)))
            print()
            
            for group in groups_to_show:
                print(f"Group #{group['id']} ({len(group['contacts'])} duplicates):")
                for i, contact in enumerate(group['contacts'], 1):
                    print(f"  {i}. {contact['name']}")
                    if contact.get('phones'):
                        print(f"     Phones: {', '.join(contact['phones'][:2])}")
                    if contact.get('emails'):
                        print(f"     Emails: {', '.join(contact['emails'][:2])}")
                print()
            
            if len(groups) > max_groups_to_show:
                print(f"... and {len(groups) - max_groups_to_show} more groups")
                print()
        
        print("=" * 80)
        print()
    
    def save_preview_to_file(self, output_path: Path, preview_data: Dict[str, Any] = None) -> None:
        """
        Save preview data to a JSON file.
        
        Args:
            output_path: Path where preview should be saved
            preview_data: Preview data dictionary (uses self.preview_data if None)
        """
        import json
        
        if preview_data is None:
            preview_data = self.preview_data
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(preview_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Preview saved to {output_path}")
    
    def display_merge_preview(
        self,
        duplicate_groups: List[List[Dict[str, Any]]],
        merged_contacts_map: Dict[int, Dict[str, Any]],
        show_all: bool = False
    ) -> bool:
        """
        Display preview of how contacts will be merged.
        
        Args:
            duplicate_groups: List of duplicate groups
            merged_contacts_map: Dictionary mapping group ID to merged contact
            show_all: If True, show all groups; if False, show first 10 and ask
        
        Returns:
            True if user wants to proceed, False otherwise
        """
        print("\n" + "=" * 80)
        print("MERGE PREVIEW")
        print("=" * 80)
        print()
        
        max_groups_to_show = 10
        groups_to_show = duplicate_groups if show_all else duplicate_groups[:max_groups_to_show]
        
        for group_id, group in enumerate(groups_to_show, 1):
            merged = merged_contacts_map.get(group_id)
            if not merged:
                continue
            
            print(f"Group #{group_id} → Merged Contact:")
            print(f"  Name: {merged.get('name', 'Unknown')}")
            
            phones = merged.get('phones', [])
            if phones:
                phone_str = ', '.join([p.get('number', '') for p in phones[:3]])
                if len(phones) > 3:
                    phone_str += f" (+{len(phones) - 3} more)"
                print(f"  Phones: {phone_str}")
            
            emails = merged.get('emails', [])
            if emails:
                email_str = ', '.join([e.get('address', '') for e in emails[:3]])
                if len(emails) > 3:
                    email_str += f" (+{len(emails) - 3} more)"
                print(f"  Emails: {email_str}")
            
            print(f"  Source contacts: {len(group)}")
            print()
        
        if not show_all and len(duplicate_groups) > max_groups_to_show:
            print(f"... and {len(duplicate_groups) - max_groups_to_show} more groups")
            print()
            print("=" * 80)
            print()
            
            # Ask if user wants to see all merges
            response = input(f"Show all {len(duplicate_groups)} merge previews? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                print("\n" + "=" * 80)
                print("ALL MERGE PREVIEWS")
                print("=" * 80)
                print()
                # Recursively call to show all
                for group_id, group in enumerate(duplicate_groups, 1):
                    merged = merged_contacts_map.get(group_id)
                    if not merged:
                        continue
                    
                    print(f"Group #{group_id} → Merged Contact:")
                    print(f"  Name: {merged.get('name', 'Unknown')}")
                    
                    phones = merged.get('phones', [])
                    if phones:
                        phone_str = ', '.join([p.get('number', '') for p in phones[:3]])
                        if len(phones) > 3:
                            phone_str += f" (+{len(phones) - 3} more)"
                        print(f"  Phones: {phone_str}")
                    
                    emails = merged.get('emails', [])
                    if emails:
                        email_str = ', '.join([e.get('address', '') for e in emails[:3]])
                        if len(emails) > 3:
                            email_str += f" (+{len(emails) - 3} more)"
                        print(f"  Emails: {email_str}")
                    
                    print(f"  Source contacts: {len(group)}")
                    print()
                
                print("=" * 80)
                print()
        
        return True

