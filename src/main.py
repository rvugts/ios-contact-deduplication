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
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contact_merger import ContactMerger
from src.csv_exporter import export_contacts_to_csv
from src.duplicate_detector import DuplicateDetector
from src.logger import (
    log_duplicate_group,
    log_merge_operation,
    log_statistics,
    setup_logger,
)
from src.phone_normalizer import (
    detect_region_from_locale,
    get_default_region,
    normalize_contacts_phones,
    validate_region_code
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


def _prompt_for_normalization(logger: any) -> bool:
    """
    Prompt user whether to enable phone normalization.

    :param logger: Logger instance
    :return: True if user wants normalization, False otherwise
    """
    try:
        response = input(
            "Normalize phone numbers to E.164 format? (yes/no): "
        ).strip().lower()
        return response in ['yes', 'y']
    except (EOFError, KeyboardInterrupt):
        logger.info(
            "Non-interactive mode detected, phone normalization disabled"
        )
        return False


def _prompt_for_detected_region(detected: str) -> Optional[str]:
    """
    Prompt user to confirm detected region.

    :param detected: Auto-detected region code
    :return: Confirmed region or None if user declines
    """
    try:
        response = input(
            f"Default phone region detected as {detected}. "
            f"Use this? (yes/no) [enter for yes]: "
        ).strip().lower()
        return detected if response in ['', 'yes', 'y'] else None
    except (EOFError, KeyboardInterrupt):
        return detected


def _prompt_for_manual_region() -> Optional[str]:
    """
    Prompt user to manually enter region code.

    :return: User-entered region code or None
    """
    try:
        response = input(
            "Enter 2-letter country code for phone numbers "
            "(e.g., US, GB, NL) [enter for auto-detect]: "
        ).strip().upper()
        return response if response else None
    except (EOFError, KeyboardInterrupt):
        return None


def _validate_provided_region(provided_region: str) -> Optional[str]:
    """
    Validate and normalize a provided region code.

    :param provided_region: Region code to validate
    :return: Validated region code or None if invalid
    """
    normalized = provided_region.strip().upper()
    return normalized if validate_region_code(normalized) else None


def _get_phone_region_interactive() -> Optional[str]:
    """
    Interactively determine phone region code.

    :return: Determined region code or None
    """
    # Try auto-detection first
    detected = detect_region_from_locale()
    if detected:
        phone_region = _prompt_for_detected_region(detected)
        if phone_region:
            return phone_region

    # Manual entry if detection failed or user declined
    return _prompt_for_manual_region()


def _finalize_phone_region(
    phone_region: Optional[str],
    no_confirm: bool,
    logger: any
) -> str:
    """
    Finalize phone region determination with error handling.

    :param phone_region: Tentative phone region
    :param no_confirm: Whether confirmations are disabled
    :param logger: Logger instance
    :return: Valid region code
    :raises SystemExit: If region cannot be determined
    """
    final_region = get_default_region(
        provided_region=phone_region,
        auto_detect=True,
        require_explicit=True
    )

    if not final_region:
        error_msg = (
            "Phone region code required for normalization but "
            "--no-confirm prevents prompting. "
            "Use --phone-region to specify a 2-letter country code."
        ) if no_confirm else (
            "Could not determine phone region automatically. "
            "Please specify --phone-region or ensure locale is set."
        )
        logger.error(error_msg)
        sys.exit(1)

    logger.info(f"Using phone region code: {final_region}")
    return final_region


def _determine_phone_settings(
    args: argparse.Namespace,
    logger: any
) -> tuple[bool, Optional[str]]:
    """
    Determine phone normalization settings from arguments and user input.

    :param args: Parsed command-line arguments
    :param logger: Logger instance
    :return: Tuple of (normalize_phones, phone_region)
    """
    # Determine if normalization is enabled
    if args.normalize_phones:
        normalize_phones = True
    elif args.no_normalize_phones:
        normalize_phones = False
    elif not args.no_confirm:
        normalize_phones = _prompt_for_normalization(logger)
    else:
        normalize_phones = False

    if not normalize_phones:
        return False, None

    # Determine region code
    phone_region = None

    # Use provided region if specified
    if args.phone_region:
        phone_region = _validate_provided_region(args.phone_region)
        if not phone_region:
            logger.warning(
                f"Invalid region code '{args.phone_region}' provided. "
                f"Will use auto-detection or prompt."
            )

    # Interactive region determination if not provided
    if not phone_region and not args.no_confirm:
        phone_region = _get_phone_region_interactive()

    # Finalize and validate region
    phone_region = _finalize_phone_region(phone_region, args.no_confirm, logger)

    return True, phone_region


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


def _create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    :return: Configured argument parser
    """
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

    parser.add_argument(
        '--normalize-phones',
        action='store_true',
        default=False,
        help='Normalize phone numbers to E.164 format in output'
    )

    parser.add_argument(
        '--no-normalize-phones',
        action='store_true',
        help='Explicitly disable phone normalization (for non-interactive use)'
    )

    parser.add_argument(
        '--phone-region',
        type=str,
        default=None,
        metavar='CODE',
        help='2-letter country code for phone number parsing '
             '(e.g., US, GB, NL). If not provided, will auto-detect from '
             'system locale or prompt user.'
    )

    parser.add_argument(
        '--csv',
        '--export-csv',
        type=str,
        dest='csv_output',
        help='Export contacts to CSV file (provide path)'
    )

    return parser


def _process_contacts(
    contacts: list,
    args: argparse.Namespace,
    logger: any
) -> tuple[list, list, list]:
    """
    Process contacts to find and merge duplicates.

    :param contacts: List of contact dictionaries
    :param args: Parsed command-line arguments
    :param logger: Logger instance
    :return: Tuple of (duplicate_groups, merged_contacts_map, final_contacts)
    """
    detector = DuplicateDetector(fuzzy_threshold=args.fuzzy_threshold)
    duplicate_groups = _build_duplicate_groups(contacts, detector, logger)

    merger = ContactMerger()
    contacts_in_groups = {
        contact['_index']
        for group in duplicate_groups
        for contact in group
        if '_index' in contact
    }

    merged_contacts_map, final_contacts = _merge_duplicate_groups(
        duplicate_groups, merger, logger
    )

    _add_non_duplicate_contacts(contacts, contacts_in_groups, final_contacts)

    return duplicate_groups, merged_contacts_map, final_contacts


def _handle_phone_normalization(
    final_contacts: list,
    normalize_phones: bool,
    phone_region: Optional[str],
    logger: any
) -> list:
    """
    Normalize phone numbers if requested.

    :param final_contacts: List of contacts to normalize
    :param normalize_phones: Whether to normalize
    :param phone_region: Region code for normalization
    :param logger: Logger instance
    :return: Contacts with normalized phones
    """
    if not normalize_phones:
        return final_contacts

    logger.info(
        f"Normalizing phone numbers to E.164 format (region: {phone_region})..."
    )
    normalized_contacts, stats = normalize_contacts_phones(
        final_contacts, default_region=phone_region
    )
    logger.info(
        f"Phone normalization complete: "
        f"{stats['normalized_phones']} normalized, "
        f"{stats['failed_normalizations']} failed"
    )
    return normalized_contacts


def _handle_validation(
    output_path: Path,
    final_contacts: list,
    contacts: list,
    duplicate_groups: list,
    skip_validation: bool,
    logger: any
) -> None:
    """
    Validate output file if requested.

    :param output_path: Path to output file
    :param final_contacts: List of final contacts
    :param contacts: Original contacts list
    :param duplicate_groups: List of duplicate groups
    :param skip_validation: Whether to skip validation
    :param logger: Logger instance
    :raises SystemExit: If validation fails
    """
    if skip_validation:
        logger.info("Output validation skipped (--no-validate flag used)")
        return

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


def _handle_csv_export(
    csv_output: Optional[str],
    final_contacts: list,
    normalize_phones: bool,
    logger: any
) -> None:
    """
    Export contacts to CSV if requested.

    :param csv_output: CSV output path or None
    :param final_contacts: List of contacts to export
    :param normalize_phones: Whether phones were normalized
    :param logger: Logger instance
    """
    if not csv_output:
        return

    csv_path = Path(csv_output)
    logger.info(f"Exporting {len(final_contacts)} contacts to CSV: {csv_path}")
    export_contacts_to_csv(final_contacts, csv_path, normalize_phones)
    logger.info(f"CSV export completed: {csv_path}")


def main() -> None:
    """Main application entry point."""
    parser = _create_argument_parser()
    args = parser.parse_args()

    logger = setup_logger(log_level=args.log_level)
    preview_mode = args.preview and not args.no_preview

    _validate_fuzzy_threshold(args.fuzzy_threshold, logger)

    # Determine phone normalization and region settings
    normalize_phones, phone_region = _determine_phone_settings(args, logger)

    try:
        input_path = Path(args.input)
        logger.info(f"Reading contacts from {input_path}")
        contacts = parse_vcard_file(input_path)

        if not contacts:
            logger.error("No contacts found in input file")
            sys.exit(1)

        logger.info(f"Loaded {len(contacts)} contacts")

        # Process contacts (detect and merge duplicates)
        duplicate_groups, merged_contacts_map, final_contacts = (
            _process_contacts(contacts, args, logger)
        )

        # Normalize phone numbers if enabled
        final_contacts = _handle_phone_normalization(
            final_contacts, normalize_phones, phone_region, logger
        )

        # Generate and display preview
        preview_gen = PreviewGenerator()
        preview_data = preview_gen.generate_preview(
            duplicate_groups, len(contacts), final_contacts
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

        # Write output and validate
        output_path = Path(args.output)
        logger.info(f"Writing {len(final_contacts)} contacts to {output_path}")
        write_vcard_file(final_contacts, output_path)

        _handle_validation(
            output_path,
            final_contacts,
            contacts,
            duplicate_groups,
            args.no_validate,
            logger
        )

        # Log statistics
        stats = {
            'total_contacts': len(contacts),
            'duplicate_groups': len(duplicate_groups),
            'contacts_merged': (
                sum(len(group) for group in duplicate_groups) -
                len(duplicate_groups)
            ),
            'final_contacts': len(final_contacts),
            'reduction_percent': (
                (len(contacts) - len(final_contacts)) / len(contacts) * 100
                if contacts else 0
            )
        }
        log_statistics(logger, stats)

        logger.info("Contact deduplication completed successfully!")

        # Save preview if in preview mode
        if preview_mode:
            preview_file = output_path.parent / f"{output_path.stem}_preview.json"
            preview_gen.save_preview_to_file(preview_file, preview_data)

        # Export to CSV if requested
        _handle_csv_export(args.csv_output, final_contacts, normalize_phones, logger)

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
