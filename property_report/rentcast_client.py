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
    
    def get_sold_properties(
        self,
        latitude: float,
        longitude: float,
        radius: float = 1.0,
        sale_date_range_days: int = 180,
        bedrooms_min: Optional[int] = None,
        bedrooms_max: int = 5,
        bathrooms_min: Optional[int] = None,
        bathrooms_max: int = 4,
        sqft_min: Optional[int] = None,
        sqft_max: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 500
    ) -> list:
        """
        Fetch sold properties within a radius of a location.
        
        Uses the /properties endpoint with saleDateRange filter to find
        recently sold comparable properties.
        
        Args:
            latitude: Latitude of the center point.
            longitude: Longitude of the center point.
            radius: Search radius in miles (default 1.0).
            sale_date_range_days: Max days since sale (default 180 = 6 months).
            bedrooms_min: Minimum bedrooms filter.
            bedrooms_max: Maximum bedrooms filter (default 5).
            bathrooms_min: Minimum bathrooms filter.
            bathrooms_max: Maximum bathrooms filter (default 4).
            sqft_min: Minimum square footage.
            sqft_max: Maximum square footage.
            property_type: Property type filter.
            limit: Maximum results to return.
            
        Returns:
            List of sold property dictionaries.
        """
        # Build bedroom range (format: "min:max")
        bedroom_range = None
        if bedrooms_min is not None or bedrooms_max is not None:
            min_str = str(int(bedrooms_min)) if bedrooms_min is not None else "*"
            max_str = str(int(bedrooms_max)) if bedrooms_max is not None else "*"
            bedroom_range = f"{min_str}:{max_str}"
        
        # Build bathroom range
        bathroom_range = None
        if bathrooms_min is not None or bathrooms_max is not None:
            min_str = str(int(bathrooms_min)) if bathrooms_min is not None else "*"
            max_str = str(int(bathrooms_max)) if bathrooms_max is not None else "*"
            bathroom_range = f"{min_str}:{max_str}"
        
        # Build square footage range
        sqft_range = None
        if sqft_min is not None or sqft_max is not None:
            min_str = str(int(sqft_min)) if sqft_min is not None else "*"
            max_str = str(int(sqft_max)) if sqft_max is not None else "*"
            sqft_range = f"{min_str}:{max_str}"
        
        # saleDateRange: "*:180" means sold within last 180 days
        sale_date_range = f"*:{sale_date_range_days}"
        
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
            "saleDateRange": sale_date_range,
            "bedrooms": bedroom_range,
            "bathrooms": bathroom_range,
            "squareFootage": sqft_range,
            "propertyType": property_type,
            "limit": limit
        }
        
        logger.info(
            f"Fetching sold properties within {radius} miles of "
            f"({latitude}, {longitude}), sold in last {sale_date_range_days} days"
        )
        response = self._make_request("/properties", params)
        
        # Response is a list of properties
        if isinstance(response, list):
            logger.info(f"Found {len(response)} sold properties")
            return response
        
        return []
