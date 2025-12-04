#!/usr/bin/env python3
"""
Main entry point for the Contact Deduplication Tool.

This module provides the command-line interface for the contact deduplication
application, handling argument parsing, workflow orchestration, and user
interaction.

Dependencies:
    - argparse: Standard library for command-line argument parsing
    - sys: Standard library for system-specific parameters
    - pathlib: Standard library for path handling
    - src.vcard_parser: Local module for vCard parsing and writing
    - src.duplicate_detector: Local module for duplicate detection
    - src.contact_merger: Local module for contact merging
    - src.preview_generator: Local module for preview generation
    - src.logger: Local module for logging configuration
"""
# pylint: disable=logging-fstring-interpolation, broad-except, wrong-import-position

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contact_merger import ContactMerger
from src.duplicate_detector import DuplicateDetector
from src.logger import (
    log_duplicate_group,
    log_merge_operation,
    log_statistics,
    setup_logger,
)
from src.preview_generator import PreviewGenerator
from src.vcard_parser import (
    parse_vcard_file,
    validate_vcard_file,
    write_vcard_file,
)


def _validate_fuzzy_threshold(threshold: int, logger: any) -> None:
    """
    Validate fuzzy threshold value.

    :param threshold: Fuzzy threshold value
    :param logger: Logger instance
    :raises SystemExit: If threshold is invalid
    """
    if not 0 <= threshold <= 100:
        logger.error("Fuzzy threshold must be between 0 and 100")
        sys.exit(1)


def _build_duplicate_groups(
    contacts: list,
    detector: DuplicateDetector,
    logger: any
) -> list:
    """
    Build duplicate groups from contacts.

    :param contacts: List of contact dictionaries
    :param detector: DuplicateDetector instance
    :param logger: Logger instance
    :return: List of duplicate groups
    """
    duplicate_groups = detector.find_duplicates(contacts)

    for group_id, group in enumerate(duplicate_groups, 1):
        if len(group) >= 2:
            criteria = detector.get_match_criteria(group[0], group[1])
        else:
            criteria = "Unknown"
        log_duplicate_group(logger, group_id, group, criteria)

    return duplicate_groups


def _merge_duplicate_groups(
    duplicate_groups: list,
    merger: ContactMerger,
    logger: any
) -> tuple[dict, list]:
    """
    Merge duplicate groups into single contacts.

    :param duplicate_groups: List of duplicate groups
    :param merger: ContactMerger instance
    :param logger: Logger instance
    :return: Tuple of (merged_contacts_map, final_contacts)
    """
    merged_contacts_map = {}
    final_contacts = []

    for group_id, group in enumerate(duplicate_groups, 1):
        merged = merger.merge_contacts(group)
        merged_contacts_map[group_id] = merged
        final_contacts.append(merged)
        log_merge_operation(logger, merged, group)

    return merged_contacts_map, final_contacts


def _add_non_duplicate_contacts(
    contacts: list,
    contacts_in_groups: set,
    final_contacts: list
) -> None:
    """
    Add non-duplicate contacts to final list.

    :param contacts: Original list of contacts
    :param contacts_in_groups: Set of contact indices in duplicate groups
    :param final_contacts: List of final contacts to append to
    """
    for idx, contact in enumerate(contacts):
        if idx not in contacts_in_groups:
            clean_contact = {
                k: v for k, v in contact.items() if not k.startswith('_')
            }
            final_contacts.append(clean_contact)


def _handle_preview_mode(
    preview_mode: bool,
    preview_gen: PreviewGenerator,
    duplicate_groups: list,
    merged_contacts_map: dict,
    logger: any,
    no_confirm: bool
) -> bool:
    """
    Handle preview mode and user confirmation.

    :param preview_mode: Whether preview mode is enabled
    :param preview_gen: PreviewGenerator instance
    :param duplicate_groups: List of duplicate groups
    :param merged_contacts_map: Dictionary of merged contacts
    :param logger: Logger instance
    :param no_confirm: Whether to skip confirmation
    :return: True if should proceed, False otherwise
    """
    if not preview_mode:
        return True

    try:
        should_proceed = preview_gen.display_merge_preview(
            duplicate_groups,
            merged_contacts_map,
            show_all=False
        )

        if not should_proceed:
            logger.info("Merge cancelled by user")
            return False
    except (EOFError, KeyboardInterrupt):
        logger.info("Non-interactive mode detected, proceeding with merge")

    if not no_confirm:
        try:
            response = input("\nProceed with merge? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                logger.info("Merge cancelled by user")
                return False
        except (EOFError, KeyboardInterrupt):
            logger.info("Non-interactive mode, proceeding with merge")

    return True


def _display_validation_report(
    validation_report: dict,
    output_path: Path
) -> None:
    """
    Display validation report to console.

    :param validation_report: Validation report dictionary
    :param output_path: Path to output file
    """
    print("\n" + "=" * 80)
    print("VALIDATION REPORT")
    print("=" * 80)
    print(f"Output file: {output_path}")
    print(f"Parse successful: {validation_report['parse_successful']}")
    print(f"Input contacts: {validation_report['input_contact_count']}")
    print(
        f"Expected output contacts: "
        f"{validation_report['expected_contact_count']}"
    )
    print(f"Actual output contacts: {validation_report['output_contact_count']}")
    print(
        f"Duplicate groups merged: "
        f"{validation_report['duplicate_groups_count']}"
    )

    if 'phone_types' in validation_report:
        pt = validation_report['phone_types']
        print(
            f"Phone type preservation: {pt['phones_with_types']}/"
            f"{pt['total_phones']} phones have types "
            f"({pt['preservation_percent']:.1f}%)"
        )

    if validation_report['errors']:
        print(f"\nErrors ({len(validation_report['errors'])}):")
        for error in validation_report['errors']:
            print(f"  ✗ {error}")

    if validation_report['warnings']:
        print(f"\nWarnings ({len(validation_report['warnings'])}):")
        for warning in validation_report['warnings']:
            print(f"  ⚠ {warning}")

    if validation_report['valid']:
        print("\n✓ Validation PASSED: Output file is valid and all contacts "
              "are present")
    else:
        print("\n✗ Validation FAILED: Issues found in output file")
    print("=" * 80)


def main() -> None:
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

    logger = setup_logger(log_level=args.log_level)
    preview_mode = args.preview and not args.no_preview

    _validate_fuzzy_threshold(args.fuzzy_threshold, logger)

    try:
        input_path = Path(args.input)
        logger.info(f"Reading contacts from {input_path}")
        contacts = parse_vcard_file(input_path)

        if not contacts:
            logger.error("No contacts found in input file")
            sys.exit(1)

        logger.info(f"Loaded {len(contacts)} contacts")

        detector = DuplicateDetector(fuzzy_threshold=args.fuzzy_threshold)
        duplicate_groups = _build_duplicate_groups(contacts, detector, logger)

        merger = ContactMerger()
        contacts_in_groups = set()
        for group in duplicate_groups:
            for contact in group:
                if '_index' in contact:
                    contacts_in_groups.add(contact['_index'])

        merged_contacts_map, final_contacts = _merge_duplicate_groups(
            duplicate_groups,
            merger,
            logger
        )

        _add_non_duplicate_contacts(
            contacts,
            contacts_in_groups,
            final_contacts
        )

        preview_gen = PreviewGenerator()
        preview_data = preview_gen.generate_preview(
            duplicate_groups,
            len(contacts),
            final_contacts
        )

        if preview_mode:
            preview_gen.display_preview(preview_data)

        should_proceed = _handle_preview_mode(
            preview_mode,
            preview_gen,
            duplicate_groups,
            merged_contacts_map,
            logger,
            args.no_confirm
        )

        if not should_proceed:
            sys.exit(0)

        output_path = Path(args.output)
        logger.info(f"Writing {len(final_contacts)} contacts to {output_path}")
        write_vcard_file(final_contacts, output_path)

        if not args.no_validate:
            logger.info("Validating output file...")
            is_valid, validation_report = validate_vcard_file(
                output_path=output_path,
                expected_contact_count=len(final_contacts),
                input_contact_count=len(contacts),
                duplicate_groups_count=len(duplicate_groups)
            )

            _display_validation_report(validation_report, output_path)

            if not is_valid:
                logger.error("Validation failed - output file may have issues")
                sys.exit(1)
        else:
            logger.info("Output validation skipped (--no-validate flag used)")

        stats = {
            'total_contacts': len(contacts),
            'duplicate_groups': len(duplicate_groups),
            'contacts_merged': sum(len(group) for group in duplicate_groups) -
            len(duplicate_groups),
            'final_contacts': len(final_contacts),
            'reduction_percent': (
                (len(contacts) - len(final_contacts)) / len(contacts) * 100
                if contacts else 0
            )
        }
        log_statistics(logger, stats)

        logger.info("Contact deduplication completed successfully!")

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
