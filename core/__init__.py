"""
Core module for Egyptian Deals & Black Friday Telegram Bot.
Contains data models, enums, canonical URL normalization, and classifier.
"""

from core.models import StoreEnum, CategoryEnum, Deal, canonicalize_url, compute_deal_hash
from core.classifier import classify_deal

__all__ = [
    "StoreEnum",
    "CategoryEnum",
    "Deal",
    "canonicalize_url",
    "compute_deal_hash",
    "classify_deal",
]
