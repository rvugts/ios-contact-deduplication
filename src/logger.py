"""
Logging configuration and utilities for the contact deduplication tool.

This module provides logging setup and utility functions for structured
logging throughout the application.

Dependencies:
    - logging: Standard library for logging functionality
    - sys: Standard library for system-specific parameters
    - pathlib: Standard library for path handling
    - datetime: Standard library for date/time operations
    - typing: Standard library for type hints
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from logging import Logger


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True
) -> Logger:
    """
    Set up and configure the application logger.

    :param log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    :param log_file: Optional path to log file. If None, creates timestamped
                     log in logs/
    :param console_output: Whether to output logs to console
    :return: Configured logger instance
    """
    logger = logging.getLogger("contact_deduplication")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    logger.handlers.clear()

    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

    if log_file is None:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"deduplication_{timestamp}.log"

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    logger.info("Logging initialized. Log file: %s", log_file)

    return logger


def log_duplicate_group(
    logger: Logger,
    group_id: int,
    contacts: List[Dict[str, Any]],
    match_criteria: str
) -> None:
    """
    Log a duplicate group detection.

    :param logger: Logger instance
    :param group_id: Unique identifier for the duplicate group
    :param contacts: List of contact dictionaries in the group
    :param match_criteria: Description of how duplicates were matched
    """
    logger.info(
        f"Duplicate Group #{group_id}: Found {len(contacts)} duplicates"
    )
    logger.debug(f"  Match criteria: {match_criteria}")
    for i, contact in enumerate(contacts, 1):
        name = contact.get('name', 'Unknown')
        logger.debug(f"  Contact {i}: {name}")


def log_merge_operation(
    logger: Logger,
    merged_contact: Dict[str, Any],
    source_contacts: List[Dict[str, Any]]
) -> None:
    """
    Log a contact merge operation.

    :param logger: Logger instance
    :param merged_contact: The resulting merged contact
    :param source_contacts: List of contacts that were merged
    """
    merged_name = merged_contact.get('name', 'Unknown')
    logger.info(f"Merged {len(source_contacts)} contacts into: {merged_name}")
    source_names = [c.get('name', 'Unknown') for c in source_contacts]
    logger.debug(f"  Source contacts: {source_names}")
    logger.debug(f"  Result: {merged_name}")


def log_statistics(logger: Logger, stats: Dict[str, Any]) -> None:
    """
    Log summary statistics.

    :param logger: Logger instance
    :param stats: Dictionary containing statistics
    """
    logger.info("=" * 60)
    logger.info("PROCESSING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total contacts processed: {stats.get('total_contacts', 0)}")
    logger.info(f"Duplicate groups found: {stats.get('duplicate_groups', 0)}")
    logger.info(f"Contacts merged: {stats.get('contacts_merged', 0)}")
    logger.info(f"Final contact count: {stats.get('final_contacts', 0)}")
    reduction = stats.get('reduction_percent', 0)
    logger.info(f"Reduction: {reduction:.1f}%")
    logger.info("=" * 60)
