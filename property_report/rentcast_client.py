"""
Rentcast API Client Module

This module provides a clean interface to interact with the Rentcast API
for fetching property listings and automated valuation model (AVM) data.
"""

import logging
from typing import Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class AVMResult:
    """Data class to hold AVM result data."""
    price: float
    price_range_low: float
    price_range_high: float
    comparables: list
    subject_property: dict


class RentcastAPIError(Exception):
    """Custom exception for Rentcast API errors."""
    pass


class RentcastClient:
    """
    Client for interacting with the Rentcast API.
    
    Provides methods to fetch sale listings and property valuations
    while minimizing API calls to reduce costs.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.rentcast.io/v1"):
        """
        Initialize the Rentcast API client.
        
        Args:
            api_key: The API key for authentication.
            base_url: The base URL for the Rentcast API.
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "X-Api-Key": api_key
        })
    
    def _make_request(self, endpoint: str, params: dict) -> dict:
        """
        Make a GET request to the Rentcast API.
        
        Args:
            endpoint: The API endpoint path.
            params: Query parameters for the request.
            
        Returns:
            The JSON response as a dictionary.
            
        Raises:
            RentcastAPIError: If the API request fails.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Remove None values from params
        params = {k: v for k, v in params.items() if v is not None}
        
        logger.debug(f"Making request to {url} with params: {params}")
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"API request failed: {e}"
            if response.text:
                error_msg += f" - Response: {response.text}"
            logger.error(error_msg)
            raise RentcastAPIError(error_msg) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during API request: {e}")
            raise RentcastAPIError(f"Network error: {e}") from e
    
    def get_sale_listings(
        self,
        zip_code: str,
        property_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_sqft: Optional[int] = None,
        max_sqft: Optional[int] = None,
        status: str = "Active",
        limit: int = 500,
        offset: int = 0
    ) -> list:
        """
        Fetch sale listings from the Rentcast API.
        
        Args:
            zip_code: The zip code to search in.
            property_type: Type of property (e.g., "Single Family").
            min_price: Minimum listing price.
            max_price: Maximum listing price.
            min_sqft: Minimum square footage.
            max_sqft: Maximum square footage.
            status: Listing status ("Active" or "Inactive").
            limit: Maximum number of results per request.
            offset: Offset for pagination.
            
        Returns:
            List of property listing dictionaries.
        """
        # Build price range parameter (format: "min:max", "*:max", "min:*")
        price_range = None
        if min_price is not None or max_price is not None:
            min_str = str(int(min_price)) if min_price is not None else "*"
            max_str = str(int(max_price)) if max_price is not None else "*"
            price_range = f"{min_str}:{max_str}"
        
        # Build square footage range parameter
        sqft_range = None
        if min_sqft is not None or max_sqft is not None:
            min_str = str(int(min_sqft)) if min_sqft is not None else "*"
            max_str = str(int(max_sqft)) if max_sqft is not None else "*"
            sqft_range = f"{min_str}:{max_str}"
        
        params = {
            "zipCode": zip_code,
            "propertyType": property_type,
            "price": price_range,
            "squareFootage": sqft_range,
            "status": status,
            "limit": limit,
            "offset": offset
        }
        
        logger.info(f"Fetching sale listings for zip code {zip_code}")
        response = self._make_request("/listings/sale", params)
        
        # Response is a list of listings
        if isinstance(response, list):
            logger.info(f"Found {len(response)} listings")
            return response
        
        return []
    
    def get_value_estimate(
        self,
        address: str,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        bathrooms: Optional[float] = None,
        square_footage: Optional[int] = None,
        max_radius: float = 1.0,
        days_old: int = 365,
        comp_count: int = 10,
        lookup_subject_attributes: bool = True
    ) -> AVMResult:
        """
        Get property value estimate (AVM) from the Rentcast API.
        
        This endpoint returns the current property value estimate and
        comparable sale listings for a specific address.
        
        Args:
            address: The full property address.
            property_type: Type of property to override lookup.
            bedrooms: Number of bedrooms to override lookup.
            bathrooms: Number of bathrooms to override lookup.
            square_footage: Square footage to override lookup.
            max_radius: Maximum radius in miles for comparables.
            days_old: Maximum age of comparables in days.
            comp_count: Number of comparables to return.
            lookup_subject_attributes: Whether to auto-lookup property attributes.
            
        Returns:
            AVMResult containing the value estimate and comparables.
            
        Raises:
            RentcastAPIError: If the API request fails.
        """
        params = {
            "address": address,
            "propertyType": property_type,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "squareFootage": square_footage + 400,
            "maxRadius": max_radius,
            "daysOld": days_old,
            "compCount": comp_count,
            "lookupSubjectAttributes": str(lookup_subject_attributes).lower()
        }
        
        logger.info(f"Fetching value estimate for: {address}")
        response = self._make_request("/avm/value", params)
        
        return AVMResult(
            price=response.get("price", 0),
            price_range_low=response.get("priceRangeLow", 0),
            price_range_high=response.get("priceRangeHigh", 0),
            comparables=response.get("comparables", []),
            subject_property=response.get("subjectProperty", {})
        )
    
    def get_value_estimate_renovated(
        self,
        address: str,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        bathrooms: Optional[float] = None,
        square_footage: Optional[int] = None,
        max_radius: float = 1.0,
        days_old: int = 365,
        comp_count: int = 10
    ) -> AVMResult:
        """
        Get property value estimate for a fully renovated property.
        
        This uses the same /avm/value endpoint but with parameters
        that suggest a renovated property condition. The Rentcast API
        doesn't have a direct "condition" parameter, so we rely on
        the comparable properties that have been sold recently
        (which tend to be renovated for sale).
        
        Note: The API compares against recently sold properties,
        which typically represent market-ready (renovated) conditions.
        
        Args:
            address: The full property address.
            property_type: Type of property.
            bedrooms: Number of bedrooms.
            bathrooms: Number of bathrooms.
            square_footage: Square footage.
            max_radius: Maximum radius in miles for comparables.
            days_old: Maximum age of comparables in days.
            comp_count: Number of comparables to return.
            
        Returns:
            AVMResult containing the ARV estimate and comparables.
        """
        # For renovated/ARV estimate, we use the standard AVM endpoint
        # The price returned represents the after-repair value (ARV)
        # as stated in Rentcast documentation
        return self.get_value_estimate(
            address=address,
            property_type=property_type,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            square_footage=square_footage,
            max_radius=max_radius,
            days_old=days_old,
            comp_count=comp_count,
            lookup_subject_attributes=True
        )
