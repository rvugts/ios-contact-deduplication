#!/usr/bin/env python3
"""
Main entry point for the Contact Deduplication Tool.
"""

import argparse
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.vcard_parser import parse_vcard_file, write_vcard_file
from src.duplicate_detector import DuplicateDetector
from src.contact_merger import ContactMerger
from src.preview_generator import PreviewGenerator
from src.logger import setup_logger, log_duplicate_group, log_merge_operation, log_statistics


def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description='Merge duplicate contacts from iOS vCard export',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Path to input vCard file (.vcf)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        required=True,
        help='Path to output vCard file (.vcf)'
    )
    
    parser.add_argument(
        '--preview', '-p',
        action='store_true',
        default=True,
        help='Enable preview mode (default: True)'
    )
    
    parser.add_argument(
        '--no-preview',
        action='store_true',
        help='Disable preview mode'
    )
    
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip output validation (not recommended)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--fuzzy-threshold',
        type=int,
        default=85,
        help='Fuzzy matching threshold 0-100 (default: 85)'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Skip confirmation prompt (use with caution)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logger(log_level=args.log_level)
    
    # Determine preview mode
    preview_mode = args.preview and not args.no_preview
    
    # Validate fuzzy threshold
    if not 0 <= args.fuzzy_threshold <= 100:
        logger.error("Fuzzy threshold must be between 0 and 100")
        sys.exit(1)
    
    try:
        # Parse input file
        input_path = Path(args.input)
        logger.info(f"Reading contacts from {input_path}")
        contacts = parse_vcard_file(input_path)
        
        if not contacts:
            logger.error("No contacts found in input file")
            sys.exit(1)
        
        logger.info(f"Loaded {len(contacts)} contacts")
        
        # Detect duplicates
        detector = DuplicateDetector(fuzzy_threshold=args.fuzzy_threshold)
        duplicate_groups = detector.find_duplicates(contacts)
        
        # Log duplicate groups
        for group_id, group in enumerate(duplicate_groups, 1):
            # Get match criteria for first two contacts
            if len(group) >= 2:
                criteria = detector.get_match_criteria(group[0], group[1])
            else:
                criteria = "Unknown"
            log_duplicate_group(logger, group_id, group, criteria)
        
        # Merge contacts
        merger = ContactMerger()
        merged_contacts_map = {}
        final_contacts = []
        
        # Track which original contacts (by index) are in duplicate groups
        contacts_in_groups = set()
        for group in duplicate_groups:
            for contact in group:
                if '_index' in contact:
                    contacts_in_groups.add(contact['_index'])
        
        # Merge duplicate groups
        for group_id, group in enumerate(duplicate_groups, 1):
            merged = merger.merge_contacts(group)
            merged_contacts_map[group_id] = merged
            final_contacts.append(merged)
            log_merge_operation(logger, merged, group)
        
        # Add non-duplicate contacts
        for idx, contact in enumerate(contacts):
            if idx not in contacts_in_groups:
                # Remove normalization fields
                clean_contact = {k: v for k, v in contact.items() if not k.startswith('_')}
                final_contacts.append(clean_contact)
        
        # Generate preview
        preview_gen = PreviewGenerator()
        preview_data = preview_gen.generate_preview(
            duplicate_groups,
            len(contacts),
            final_contacts
        )
        
        # Display preview if enabled
        if preview_mode:
            preview_gen.display_preview(preview_data)
            # display_merge_preview now handles showing all and returns whether to proceed
            try:
                should_proceed = preview_gen.display_merge_preview(duplicate_groups, merged_contacts_map, show_all=False)
                
                if not should_proceed:
                    logger.info("Merge cancelled by user")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                # Non-interactive mode, proceed automatically
                logger.info("Non-interactive mode detected, proceeding with merge")
        
        # Ask for confirmation (if not already handled in merge preview)
        if preview_mode and not args.no_confirm:
            response = input("\nProceed with merge? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                logger.info("Merge cancelled by user")
                sys.exit(0)
        
        # Write output
        output_path = Path(args.output)
        logger.info(f"Writing {len(final_contacts)} contacts to {output_path}")
        write_vcard_file(final_contacts, output_path)
        
        # Validate output file
        if not args.no_validate:
            logger.info("Validating output file...")
            from src.vcard_parser import validate_vcard_file
            
            is_valid, validation_report = validate_vcard_file(
                output_path=output_path,
                expected_contact_count=len(final_contacts),
                input_contact_count=len(contacts),
                duplicate_groups_count=len(duplicate_groups)
            )
            
            # Print validation report
            print("\n" + "=" * 80)
            print("VALIDATION REPORT")
            print("=" * 80)
            print(f"Output file: {output_path}")
            print(f"Parse successful: {validation_report['parse_successful']}")
            print(f"Input contacts: {validation_report['input_contact_count']}")
            print(f"Expected output contacts: {validation_report['expected_contact_count']}")
            print(f"Actual output contacts: {validation_report['output_contact_count']}")
            print(f"Duplicate groups merged: {validation_report['duplicate_groups_count']}")
            
            if 'phone_types' in validation_report:
                pt = validation_report['phone_types']
                print(f"Phone type preservation: {pt['phones_with_types']}/{pt['total_phones']} phones have types ({pt['preservation_percent']:.1f}%)")
            
            if validation_report['errors']:
                print(f"\nErrors ({len(validation_report['errors'])}):")
                for error in validation_report['errors']:
                    print(f"  ✗ {error}")
            
            if validation_report['warnings']:
                print(f"\nWarnings ({len(validation_report['warnings'])}):")
                for warning in validation_report['warnings']:
                    print(f"  ⚠ {warning}")
            
            if is_valid:
                print("\n✓ Validation PASSED: Output file is valid and all contacts are present")
                print("=" * 80)
            else:
                print("\n✗ Validation FAILED: Issues found in output file")
                print("=" * 80)
                logger.error("Validation failed - output file may have issues")
                sys.exit(1)
        else:
            logger.info("Output validation skipped (--no-validate flag used)")
        
        # Log statistics
        stats = {
            'total_contacts': len(contacts),
            'duplicate_groups': len(duplicate_groups),
            'contacts_merged': sum(len(group) for group in duplicate_groups) - len(duplicate_groups),
            'final_contacts': len(final_contacts),
            'reduction_percent': ((len(contacts) - len(final_contacts)) / len(contacts) * 100) if contacts else 0
        }
        log_statistics(logger, stats)
        
        logger.info("Contact deduplication completed successfully!")
        
        # Save preview to file
        if preview_mode:
            preview_file = output_path.parent / f"{output_path.stem}_preview.json"
            preview_gen.save_preview_to_file(preview_file, preview_data)
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

