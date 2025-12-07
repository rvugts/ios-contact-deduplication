"""
Phone number normalization module for E.164 format conversion.

This module provides functionality to normalize phone numbers to the international
E.164 format (e.g., +31612345678) while preserving phone type information.

The default region is used to interpret phone numbers that don't have an
international prefix (+). For example, "415 555 1234" needs a default region
to determine if it's a US number (area code 415) or formatted differently.
Numbers with a '+' prefix are parsed independently of the default region.

Dependencies:
    - phonenumbers: Third-party library for phone number parsing and formatting
    - typing: Standard library for type hints
    - logging: Standard library for logging
    - locale: Standard library for locale detection
"""
# pylint: disable=logging-fstring-interpolation

import locale
import logging
from typing import Any, Dict, List, Optional, Tuple

import phonenumbers
from phonenumbers import NumberParseException

logger = logging.getLogger("contact_deduplication")

DEFAULT_REGION = "US"


def detect_region_from_locale() -> Optional[str]:
    """
    Detect default phone region from system locale settings.

    Attempts to extract a 2-letter country code from the system's locale
    settings. This provides a reasonable default when no region is specified.

    :return: 2-letter country code (e.g., "US", "GB", "NL") or None
    """
    try:
        locale_code, _ = locale.getlocale()
        if locale_code:
            # Extract country code from locale (e.g., "en_US" -> "US")
            parts = locale_code.split('_')
            if len(parts) >= 2:
                country_code = parts[-1].upper()
                # Validate it's a reasonable length (2-3 characters)
                if 2 <= len(country_code) <= 3:
                    logger.debug(
                        f"Detected region from locale: {country_code}"
                    )
                    return country_code
    except (ValueError, AttributeError, IndexError) as e:
        logger.debug(f"Could not detect region from locale: {e}")

    return None


def validate_region_code(region_code: str) -> bool:
    """
    Validate that a region code is a valid 2-letter country code.

    :param region_code: Region code to validate
    :return: True if valid, False otherwise
    """
    if not region_code or len(region_code) != 2:
        return False

    # Check if it's alphabetic and uppercase
    if not region_code.isalpha() or not region_code.isupper():
        return False

    # Try to validate using phonenumbers library
    try:
        # Attempt to parse with region - this will throw if region invalid
        phonenumbers.parse("1234567890", region_code)
        # If we get here, the region code is at least recognized
        return True
    except NumberParseException:
        # Region code not recognized by phonenumbers library
        return False


def get_default_region(
    provided_region: Optional[str] = None,
    auto_detect: bool = True,
    require_explicit: bool = False
) -> Optional[str]:
    """
    Get the default phone region code with fallback logic.

    Priority order:
    1. Provided region code (if valid)
    2. Auto-detected region from locale (if auto_detect is True)
    3. Return None if require_explicit is True (no default fallback)
    4. Fallback to DEFAULT_REGION ("US") only if require_explicit is False

    :param provided_region: Explicitly provided region code (2-letter)
    :param auto_detect: Whether to attempt auto-detection from locale
    :param require_explicit: If True, return None instead of defaulting to US
    :return: Valid region code (2-letter country code) or None
    """
    # Use provided region if valid
    if provided_region:
        provided_region = provided_region.strip().upper()
        if validate_region_code(provided_region):
            logger.info(f"Using provided region code: {provided_region}")
            return provided_region
        logger.warning(
            f"Invalid region code '{provided_region}', "
            f"falling back to detection"
        )

    # Try auto-detection if enabled
    if auto_detect:
        detected = detect_region_from_locale()
        if detected and validate_region_code(detected):
            logger.info(f"Using auto-detected region code: {detected}")
            return detected

    # Require explicit input if specified
    if require_explicit:
        logger.warning(
            "Could not determine phone region automatically. "
            "Explicit region code required."
        )
        return None

    # Last resort: fallback to US (but log a warning)
    logger.warning(
        f"Could not determine phone region automatically, "
        f"falling back to {DEFAULT_REGION}. "
        f"This may cause incorrect normalization for non-US numbers. "
        f"Consider specifying --phone-region explicitly."
    )
    return DEFAULT_REGION


def _parse_and_format_phone(
    phone_number: str,
    region: Optional[str]
) -> Optional[str]:
    """
    Parse and format a phone number to E.164 format.

    The phonenumbers library automatically removes the leading zero (national
    trunk prefix) and adds the appropriate country code when the correct region
    is provided.

    :param phone_number: Phone number string to parse
    :param region: Region code for parsing (None for international format)
    :return: Normalized phone number in E.164 format, or None if invalid
    """
    try:
        parsed = phonenumbers.parse(phone_number, region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164
            )
    except NumberParseException:
        pass
    return None


def normalize_phone_to_e164(
    phone_number: str,
    default_region: str = DEFAULT_REGION
) -> Optional[str]:
    """
    Normalize a phone number to E.164 international format.

    E.164 format: +[country code][number] (e.g., +31612345678, +12125551234)
    The number is returned without spaces for consistency.

    This function correctly handles leading zeros in national format numbers.
    For example, "0646432757" (Dutch national format) with region "NL" will be
    normalized to "+31646432757" (the leading zero is removed and country code
    is added). The phonenumbers library handles this conversion automatically
    when the correct region code is provided.

    :param phone_number: Original phone number string
    :param default_region: Default region code for parsing
    :return: Normalized phone number in E.164 format, or None if invalid
    """
    if not phone_number or not phone_number.strip():
        return None

    phone_number = phone_number.strip()

    # Try parsing with default region first (handles leading zeros)
    normalized = _parse_and_format_phone(phone_number, default_region)
    if normalized:
        return normalized

    # Try parsing without region (for numbers with country code)
    if phone_number.startswith('+'):
        normalized = _parse_and_format_phone(phone_number, None)
        if normalized:
            return normalized

    # If all parsing attempts fail, return None
    logger.debug(f"Could not normalize phone number: {phone_number}")
    return None


def _process_phone_normalization(
    phone: Dict[str, Any],
    contact_name: str,
    default_region: str
) -> Tuple[Dict[str, Any], bool]:
    """
    Process normalization of a single phone number.

    :param phone: Phone dictionary to normalize
    :param contact_name: Name of the contact (for logging)
    :param default_region: Default region code for parsing
    :return: Tuple of (normalized phone dictionary, success flag)
    """
    phone_copy = phone.copy()
    original_number = phone.get('number', '')

    if not original_number:
        return phone_copy, False

    normalized_number = normalize_phone_to_e164(
        original_number,
        default_region
    )

    if normalized_number:
        phone_copy['number'] = normalized_number
        return phone_copy, True

    # Keep original number if normalization fails
    logger.debug(
        f"Could not normalize phone number '{original_number}' "
        f"for contact '{contact_name}', keeping original format"
    )
    return phone_copy, False


def normalize_contact_phones(
    contact: Dict[str, Any],
    default_region: str = DEFAULT_REGION
) -> Tuple[Dict[str, Any], int, int]:
    """
    Normalize all phone numbers in a contact to E.164 format.

    This function preserves phone type information while normalizing the
    phone number format. If normalization fails for a phone number, the
    original format is preserved.

    :param contact: Contact dictionary with 'phones' list
    :param default_region: Default region code for parsing
    :return: Tuple of (normalized contact dictionary,
                       normalized count, failed count)
    """
    if 'phones' not in contact or not contact['phones']:
        return contact, 0, 0

    normalized_contact = contact.copy()
    contact_name = contact.get('name', 'Unknown')
    normalized_count = 0
    failed_count = 0

    normalized_phones = []
    for phone in contact['phones']:
        phone_copy, success = _process_phone_normalization(
            phone, contact_name, default_region
        )
        normalized_phones.append(phone_copy)

        if success:
            normalized_count += 1
        else:
            failed_count += 1

    normalized_contact['phones'] = normalized_phones

    return normalized_contact, normalized_count, failed_count


def normalize_contacts_phones(
    contacts: List[Dict[str, Any]],
    default_region: str = DEFAULT_REGION
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Normalize phone numbers for a list of contacts.

    :param contacts: List of contact dictionaries
    :param default_region: Default region code for parsing
    :return: Tuple of (normalized contacts list, statistics dictionary)
    """
    stats = {
        'total_contacts': len(contacts),
        'contacts_with_phones': 0,
        'total_phones': 0,
        'normalized_phones': 0,
        'failed_normalizations': 0
    }

    normalized_contacts = []
    for contact in contacts:
        original_phones = contact.get('phones', [])
        if original_phones:
            stats['contacts_with_phones'] += 1
            stats['total_phones'] += len(original_phones)

        normalized_contact, normalized_count, failed_count = (
            normalize_contact_phones(contact, default_region)
        )

        stats['normalized_phones'] += normalized_count
        stats['failed_normalizations'] += failed_count

        normalized_contacts.append(normalized_contact)

    logger.info(
        f"Phone normalization statistics: "
        f"{stats['normalized_phones']}/{stats['total_phones']} phones normalized, "
        f"{stats['failed_normalizations']} failed"
    )

    return normalized_contacts, stats
