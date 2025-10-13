#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Log reader module for Phase 1 implementation.

Provides direct file reading with size limits for LLM analysis.
"""

import os
from typing import List, Tuple, Dict


def read_logs_for_analysis(
    log_files: List[str],
    max_lines_per_file: int = 5000,
    max_line_length: int = 2000
) -> Dict[str, any]:
    """Read log files with size limits for LLM analysis.

    This is Phase 1 implementation: simple direct reading with truncation.
    Suitable for small to medium log files.

    Args:
        log_files: List of absolute paths to log files
        max_lines_per_file: Maximum lines to read per file (default: 5000)
        max_line_length: Maximum characters per line (default: 2000)

    Returns:
        Dictionary containing:
            - content: Formatted log content string for LLM
            - metadata: Statistics about the logs read
            - warnings: List of any warnings (truncations, errors)
    """
    if not log_files:
        return {
            'content': "No log files provided.",
            'metadata': {'total_files': 0, 'total_lines': 0},
            'warnings': []
        }

    result_lines = []
    metadata = {
        'total_files': len(log_files),
        'total_lines': 0,
        'files_processed': [],
        'files_truncated': [],
        'files_with_errors': []
    }
    warnings = []

    for log_file in log_files:
        file_name = os.path.basename(log_file)
        result_lines.append(f"\n{'='*70}")
        result_lines.append(f"LOG FILE: {file_name}")
        result_lines.append(f"Full path: {log_file}")
        result_lines.append(f"{'='*70}\n")

        try:
            # Check if file exists
            if not os.path.exists(log_file):
                error_msg = f"File not found: {log_file}"
                result_lines.append(f"[ERROR: {error_msg}]\n")
                warnings.append(error_msg)
                metadata['files_with_errors'].append(file_name)
                continue

            # Check if file is readable
            if not os.path.isfile(log_file):
                error_msg = f"Not a file: {log_file}"
                result_lines.append(f"[ERROR: {error_msg}]\n")
                warnings.append(error_msg)
                metadata['files_with_errors'].append(file_name)
                continue

            # Get file size for info
            file_size = os.path.getsize(log_file)
            file_size_mb = file_size / (1024 * 1024)

            # Read the file
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            total_lines = len(lines)
            metadata['total_lines'] += min(total_lines, max_lines_per_file)

            # Check if truncation is needed
            truncated = total_lines > max_lines_per_file

            if truncated:
                warning_msg = f"File {file_name} truncated: showing first {max_lines_per_file} of {total_lines} lines"
                result_lines.append(f"[TRUNCATED: Showing first {max_lines_per_file} of {total_lines} lines]\n")
                result_lines.append(f"[File size: {file_size_mb:.2f} MB]\n\n")
                warnings.append(warning_msg)
                metadata['files_truncated'].append(file_name)
                lines = lines[:max_lines_per_file]
            else:
                result_lines.append(f"[Complete file: {total_lines} lines, {file_size_mb:.2f} MB]\n\n")

            # Add line numbers for citations
            for i, line in enumerate(lines, 1):
                # Truncate very long lines
                if len(line) > max_line_length:
                    line = line[:max_line_length] + "... [line truncated]\n"

                # Add line number for easy citation
                result_lines.append(f"{i:6d}: {line}")

            metadata['files_processed'].append({
                'name': file_name,
                'lines': min(total_lines, max_lines_per_file),
                'size_mb': file_size_mb,
                'truncated': truncated
            })

        except PermissionError:
            error_msg = f"Permission denied reading {log_file}"
            result_lines.append(f"[ERROR: {error_msg}]\n")
            warnings.append(error_msg)
            metadata['files_with_errors'].append(file_name)

        except UnicodeDecodeError as e:
            error_msg = f"Encoding error in {log_file}: {str(e)}"
            result_lines.append(f"[ERROR: {error_msg}]\n")
            result_lines.append("[Tip: File may be binary or use non-UTF-8 encoding]\n")
            warnings.append(error_msg)
            metadata['files_with_errors'].append(file_name)

        except Exception as e:
            error_msg = f"Error reading {log_file}: {str(e)}"
            result_lines.append(f"[ERROR: {error_msg}]\n")
            warnings.append(error_msg)
            metadata['files_with_errors'].append(file_name)

    content = ''.join(result_lines)

    return {
        'content': content,
        'metadata': metadata,
        'warnings': warnings
    }


def estimate_token_count(text: str) -> int:
    """Rough estimate of token count for a text string.

    Uses simple heuristic: ~4 characters per token on average.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    return len(text) // 4


def get_log_summary(log_data: Dict) -> str:
    """Create a human-readable summary of log reading results.

    Args:
        log_data: Dictionary returned by read_logs_for_analysis

    Returns:
        Formatted summary string
    """
    metadata = log_data['metadata']
    warnings = log_data['warnings']

    summary_lines = [
        "\n" + "="*70,
        "LOG READING SUMMARY",
        "="*70,
        f"Files processed: {metadata['total_files']}",
        f"Total lines read: {metadata['total_lines']}",
        f"Estimated tokens: ~{estimate_token_count(log_data['content']):,}"
    ]

    if metadata['files_truncated']:
        summary_lines.append(f"\nTruncated files: {', '.join(metadata['files_truncated'])}")

    if metadata['files_with_errors']:
        summary_lines.append(f"\nFiles with errors: {', '.join(metadata['files_with_errors'])}")

    if warnings:
        summary_lines.append(f"\nWarnings ({len(warnings)}):")
        for warning in warnings[:5]:  # Show first 5 warnings
            summary_lines.append(f"  - {warning}")
        if len(warnings) > 5:
            summary_lines.append(f"  ... and {len(warnings) - 5} more")

    summary_lines.append("="*70 + "\n")

    return '\n'.join(summary_lines)
