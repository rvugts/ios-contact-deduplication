"""
Logging configuration and utilities for the contact deduplication tool.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True
) -> logging.Logger:
    """
    Set up and configure the application logger.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file. If None, creates timestamped log in logs/
        console_output: Whether to output logs to console
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("contact_deduplication")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
    
    # File handler
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
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    
    return logger


def log_duplicate_group(logger: logging.Logger, group_id: int, contacts: list, match_criteria: str):
    """
    Log a duplicate group detection.
    
    Args:
        logger: Logger instance
        group_id: Unique identifier for the duplicate group
        contacts: List of contact dictionaries in the group
        match_criteria: Description of how duplicates were matched
    """
    logger.info(f"Duplicate Group #{group_id}: Found {len(contacts)} duplicates")
    logger.debug(f"  Match criteria: {match_criteria}")
    for i, contact in enumerate(contacts, 1):
        name = contact.get('name', 'Unknown')
        logger.debug(f"  Contact {i}: {name}")


def log_merge_operation(logger: logging.Logger, merged_contact: dict, source_contacts: list):
    """
    Log a contact merge operation.
    
    Args:
        logger: Logger instance
        merged_contact: The resulting merged contact
        source_contacts: List of contacts that were merged
    """
    merged_name = merged_contact.get('name', 'Unknown')
    logger.info(f"Merged {len(source_contacts)} contacts into: {merged_name}")
    logger.debug(f"  Source contacts: {[c.get('name', 'Unknown') for c in source_contacts]}")
    logger.debug(f"  Result: {merged_name}")


def log_statistics(logger: logging.Logger, stats: dict):
    """
    Log summary statistics.
    
    Args:
        logger: Logger instance
        stats: Dictionary containing statistics
    """
    logger.info("=" * 60)
    logger.info("PROCESSING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total contacts processed: {stats.get('total_contacts', 0)}")
    logger.info(f"Duplicate groups found: {stats.get('duplicate_groups', 0)}")
    logger.info(f"Contacts merged: {stats.get('contacts_merged', 0)}")
    logger.info(f"Final contact count: {stats.get('final_contacts', 0)}")
    logger.info(f"Reduction: {stats.get('reduction_percent', 0):.1f}%")
    logger.info("=" * 60)

