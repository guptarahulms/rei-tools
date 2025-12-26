"""
Property Report Generator Package

This package provides tools for generating daily property investment
reports using the Rentcast API.
"""

from .rentcast_client import RentcastClient, AVMResult, RentcastAPIError
from .report_generator import ReportGenerator, PropertyAnalysis
from .email_service import EmailService, EmailServiceError
from .config_manager import ConfigManager, ConfigurationError, AppConfig

__all__ = [
    "RentcastClient",
    "AVMResult",
    "RentcastAPIError",
    "ReportGenerator",
    "PropertyAnalysis",
    "EmailService",
    "EmailServiceError",
    "ConfigManager",
    "ConfigurationError",
    "AppConfig",
]

__version__ = "1.0.0"
