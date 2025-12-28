"""
Configuration Manager Module

This module handles reading and parsing the configuration file
for the property report generator.
"""

import configparser
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RentcastConfig:
    """Configuration for Rentcast API."""
    api_key: str
    base_url: str = "https://api.rentcast.io/v1"
    max_api_calls: int = 50


@dataclass
class ZipCodeConfig:
    """Configuration for a specific zip code."""
    zip_code: str
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_sqft: Optional[int] = None
    max_sqft: Optional[int] = None


@dataclass
class FilterConfig:
    """Configuration for property filtering."""
    zip_codes: list[ZipCodeConfig]
    property_types: list[str]
    status: str = "Active"
    limit: int = 500


@dataclass
class AVMConfig:
    """Configuration for AVM parameters."""
    max_radius: float = 1.0
    days_old: int = 365
    comp_count: int = 10


@dataclass
class CostConfig:
    """Configuration for cost calculations."""
    build_up_cost_per_sqft: float = 75.0
    financing_rate: float = 0.12


@dataclass
class DecisionConfig:
    """Configuration for decision criteria."""
    upside_threshold: float = 30000.0
    comp_price_threshold: float = 500000.0


@dataclass
class EmailConfig:
    """Configuration for email settings."""
    smtp_server: str
    smtp_port: int
    sender_email: str
    sender_password: str
    recipient_emails: list[str]
    subject: str = "Daily Property Investment Report"


@dataclass
class AppConfig:
    """Complete application configuration."""
    rentcast: RentcastConfig
    filters: FilterConfig
    avm: AVMConfig
    costs: CostConfig
    decision: DecisionConfig
    email: EmailConfig


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""
    pass


class ConfigManager:
    """
    Manages reading and parsing the application configuration.
    
    Reads from a config.ini file and provides typed configuration objects.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the config.ini file.
                        Defaults to config.ini in the same directory.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config.ini"
        
        self.config_path = Path(config_path)
        self._config = configparser.ConfigParser()
        self._loaded = False
    
    def _load_config(self) -> None:
        """Load the configuration file."""
        if not self.config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}"
            )
        
        logger.info(f"Loading configuration from {self.config_path}")
        self._config.read(self.config_path)
        self._loaded = True
    
    def _get_value(
        self,
        section: str,
        key: str,
        default: Optional[str] = None,
        required: bool = False
    ) -> Optional[str]:
        """
        Get a configuration value.
        
        Args:
            section: The configuration section name.
            key: The configuration key.
            default: Default value if not found.
            required: Whether the value is required.
            
        Returns:
            The configuration value or default.
            
        Raises:
            ConfigurationError: If required value is missing.
        """
        if not self._loaded:
            self._load_config()
        
        try:
            value = self._config.get(section, key)
            return value.strip() if value else default
        except (configparser.NoSectionError, configparser.NoOptionError):
            if required:
                raise ConfigurationError(
                    f"Missing required configuration: [{section}] {key}"
                )
            return default
    
    def _parse_list(self, value: Optional[str]) -> list[str]:
        """Parse a comma-separated string into a list."""
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def _parse_float(self, value: Optional[str], default: float = 0.0) -> float:
        """Parse a string to float."""
        if not value:
            return default
        try:
            return float(value)
        except ValueError:
            return default
    
    def _parse_int(self, value: Optional[str], default: int = 0) -> int:
        """Parse a string to int."""
        if not value:
            return default
        try:
            return int(float(value))
        except ValueError:
            return default
    
    def _parse_range(
        self, 
        value: Optional[str], 
        parse_as_int: bool = False
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Parse a range string in format 'min:max' into (min, max) tuple.
        
        Args:
            value: String in format 'min:max', 'min:*', '*:max', or '*:*'
            parse_as_int: If True, parse values as integers
            
        Returns:
            Tuple of (min_value, max_value). None for '*' or missing values.
        """
        if not value:
            return None, None
        
        if ':' not in value:
            # Single value - treat as both min and max
            try:
                val = int(float(value)) if parse_as_int else float(value)
                return val, val
            except ValueError:
                return None, None
        
        parts = value.split(':', 1)
        min_str = parts[0].strip()
        max_str = parts[1].strip() if len(parts) > 1 else '*'
        
        min_val = None
        max_val = None
        
        if min_str and min_str != '*':
            try:
                min_val = int(float(min_str)) if parse_as_int else float(min_str)
            except ValueError:
                pass
        
        if max_str and max_str != '*':
            try:
                max_val = int(float(max_str)) if parse_as_int else float(max_str)
            except ValueError:
                pass
        
        return min_val, max_val
    
    def get_rentcast_config(self) -> RentcastConfig:
        """Get Rentcast API configuration."""
        return RentcastConfig(
            api_key=self._get_value("rentcast", "api_key", required=True),
            base_url=self._get_value(
                "rentcast", "base_url", 
                default="https://api.rentcast.io/v1"
            ),
            max_api_calls=self._parse_int(
                self._get_value("rentcast", "max_api_calls"), default=50
            )
        )
    
    def get_filter_config(self) -> FilterConfig:
        """Get property filter configuration."""
        if not self._loaded:
            self._load_config()
        
        # Find all zip code sections (format: zipcode_XXXXX)
        zip_code_configs = []
        for section in self._config.sections():
            if section.startswith("zipcode_"):
                zip_code = section.replace("zipcode_", "")
                
                # Parse price and sqft ranges (format: min:max)
                price_min, price_max = self._parse_range(
                    self._get_value(section, "price")
                )
                sqft_min, sqft_max = self._parse_range(
                    self._get_value(section, "sqft"), parse_as_int=True
                )
                
                zip_config = ZipCodeConfig(
                    zip_code=zip_code,
                    min_price=price_min,
                    max_price=price_max,
                    min_sqft=sqft_min,
                    max_sqft=sqft_max
                )
                zip_code_configs.append(zip_config)
        
        if not zip_code_configs:
            raise ConfigurationError(
                "At least one zip code section is required (e.g., [zipcode_19143])"
            )
        
        # Parse property_types as a list (comma-separated)
        property_types = self._parse_list(
            self._get_value("filters", "property_types")
        )
        
        return FilterConfig(
            zip_codes=zip_code_configs,
            property_types=property_types,
            status=self._get_value("filters", "status", default="Active"),
            limit=self._parse_int(
                self._get_value("filters", "limit"), default=500
            )
        )
    
    def get_avm_config(self) -> AVMConfig:
        """Get AVM configuration."""
        return AVMConfig(
            max_radius=self._parse_float(
                self._get_value("avm", "max_radius"), default=1.0
            ),
            days_old=self._parse_int(
                self._get_value("avm", "days_old"), default=365
            ),
            comp_count=self._parse_int(
                self._get_value("avm", "comp_count"), default=10
            )
        )
    
    def get_cost_config(self) -> CostConfig:
        """Get cost calculation configuration."""
        return CostConfig(
            build_up_cost_per_sqft=self._parse_float(
                self._get_value("costs", "build_up_cost_per_sqft"), default=75.0
            ),
            financing_rate=self._parse_float(
                self._get_value("costs", "financing_rate"), default=0.12
            )
        )
    
    def get_decision_config(self) -> DecisionConfig:
        """Get decision criteria configuration."""
        return DecisionConfig(
            upside_threshold=self._parse_float(
                self._get_value("decision", "upside_threshold"), default=30000.0
            ),
            comp_price_threshold=self._parse_float(
                self._get_value("decision", "comp_price_threshold"), default=500000.0
            )
        )
    
    def get_email_config(self) -> EmailConfig:
        """Get email configuration."""
        recipient_emails = self._parse_list(
            self._get_value("email", "recipient_emails", required=True)
        )
        
        if not recipient_emails:
            raise ConfigurationError("At least one recipient email is required")
        
        return EmailConfig(
            smtp_server=self._get_value("email", "smtp_server", required=True),
            smtp_port=self._parse_int(
                self._get_value("email", "smtp_port"), default=587
            ),
            sender_email=self._get_value("email", "sender_email", required=True),
            sender_password=self._get_value("email", "sender_password", required=True),
            recipient_emails=recipient_emails,
            subject=self._get_value(
                "email", "subject", 
                default="Daily Property Investment Report"
            )
        )
    
    def get_app_config(self) -> AppConfig:
        """Get complete application configuration."""
        return AppConfig(
            rentcast=self.get_rentcast_config(),
            filters=self.get_filter_config(),
            avm=self.get_avm_config(),
            costs=self.get_cost_config(),
            decision=self.get_decision_config(),
            email=self.get_email_config()
        )
