"""
Log processing module for iExplain.

This module provides utilities for reading, filtering, and processing log files
for analysis by the multi-agent system.

Phase 1: Direct reading with size limits (current)
Phase 2: Intent-guided filtering and sampling (future)
Phase 3: Drain algorithm integration (future)
Phase 4: Two-pass analysis (future)
"""

from .log_reader import read_logs_for_analysis, get_log_summary, estimate_token_count

__all__ = ['read_logs_for_analysis', 'get_log_summary', 'estimate_token_count']
