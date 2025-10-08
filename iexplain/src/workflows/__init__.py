"""
Workflow orchestration module for iExplain.

This module provides different conversation patterns for agent interaction:
- Sequential: Step-by-step agent collaboration with carryover
- Nested: Complex workflows with nested sub-conversations
- GroupChat: Free-form multi-agent collaboration
"""

from .base_workflow import BaseWorkflow
from .sequential_workflow import SequentialWorkflow
from .nested_workflow import NestedWorkflow
from .groupchat_workflow import GroupchatWorkflow

__all__ = ['BaseWorkflow', 'SequentialWorkflow', 'NestedWorkflow', 'GroupchatWorkflow']
