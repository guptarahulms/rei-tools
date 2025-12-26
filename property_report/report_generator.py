"""
Property Report Generator Module

This module generates investment property reports by analyzing
properties for sale and calculating potential investment returns.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .rentcast_client import RentcastClient, AVMResult, RentcastAPIError

logger = logging.getLogger(__name__)


@dataclass
class PropertyAnalysis:
    """Data class to hold the complete analysis of a property."""
    # Basic property info
    address: str
    zip_code: str
    list_price: float
    square_footage: int
    property_type: str
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    
    # Best Offer Analysis (current condition comparables)
    best_offer_price: float = 0.0
    best_offer_comparables: list = field(default_factory=list)
    
    # Cost calculations
    build_up_cost: float = 0.0
    financing_cost: float = 0.0
    all_inclusive_cost: float = 0.0  # ARV = Best Offer + Build Up + Financing
    
    # Upside Analysis (renovated condition comparables)
    upside_value: float = 0.0  # After-repair value from renovated comps
    upside_comparables: list = field(default_factory=list)
    
    # Decision
    upside_profit: float = 0.0  # Upside - All Inclusive Cost
    decision: str = "No"
    
    # Error tracking
    error_message: Optional[str] = None


class ReportGenerator:
    """
    Generates property investment reports using Rentcast API data.
    
    This class fetches property listings, calculates investment metrics,
    and generates reports sorted by upside potential.
    """
    
    def __init__(
        self,
        rentcast_client: RentcastClient,
        build_up_cost_per_sqft: float = 75.0,
        financing_rate: float = 0.12,
        upside_threshold: float = 30000.0,
        avm_max_radius: float = 1.0,
        avm_days_old: int = 365,
        avm_comp_count: int = 10
    ):
        """
        Initialize the report generator.
        
        Args:
            rentcast_client: Configured Rentcast API client.
            build_up_cost_per_sqft: Cost per square foot for renovation.
            financing_rate: Financing cost as a percentage (e.g., 0.12 = 12%).
            upside_threshold: Minimum profit threshold for "Yes" decision.
            avm_max_radius: Maximum radius for AVM comparables (miles).
            avm_days_old: Maximum age of AVM comparables (days).
            avm_comp_count: Number of AVM comparables to fetch.
        """
        self.client = rentcast_client
        self.build_up_cost_per_sqft = build_up_cost_per_sqft
        self.financing_rate = financing_rate
        self.upside_threshold = upside_threshold
        self.avm_max_radius = avm_max_radius
        self.avm_days_old = avm_days_old
        self.avm_comp_count = avm_comp_count
    
    def _calculate_costs(
        self,
        best_offer_price: float,
        square_footage: int
    ) -> tuple[float, float, float]:
        """
        Calculate build-up cost, financing cost, and all-inclusive cost.
        
        Args:
            best_offer_price: The best offer price for the property.
            square_footage: The property's square footage.
            
        Returns:
            Tuple of (build_up_cost, financing_cost, all_inclusive_cost).
        """
        # Build Up Cost = configured per sqft cost * square footage
        build_up_cost = self.build_up_cost_per_sqft * square_footage
        
        # Financing Cost = 12% of (Best Offer Price + Build Up Cost)
        financing_cost = self.financing_rate * (best_offer_price + build_up_cost)
        
        # All Inclusive Cost (ARV) = Best Offer + Build Up + Financing
        all_inclusive_cost = best_offer_price + build_up_cost + financing_cost
        
        return build_up_cost, financing_cost, all_inclusive_cost
    
    def _format_comparable_addresses(self, comparables: list) -> list[str]:
        """
        Extract formatted addresses from comparable properties.
        
        Args:
            comparables: List of comparable property dictionaries.
            
        Returns:
            List of formatted address strings.
        """
        return [
            comp.get("formattedAddress", "Unknown")
            for comp in comparables[:5]  # Limit to top 5 for brevity
        ]
    
    def _analyze_property(self, listing: dict) -> PropertyAnalysis:
        """
        Perform complete investment analysis on a single property.
        
        This makes the minimum necessary API calls:
        - One call to get value estimate (used for best offer price)
        - The same endpoint returns ARV (after-repair value) which represents
          the upside value for renovated properties
        
        Args:
            listing: Property listing dictionary from the Sale Listings API.
            
        Returns:
            PropertyAnalysis with all calculated metrics.
        """
        address = listing.get("formattedAddress", "")
        zip_code = listing.get("zipCode", "")
        list_price = listing.get("price", 0)
        square_footage = listing.get("squareFootage", 0) or 1000  # Default if missing
        property_type = listing.get("propertyType", "Single Family")
        bedrooms = listing.get("bedrooms")
        bathrooms = listing.get("bathrooms")
        
        analysis = PropertyAnalysis(
            address=address,
            zip_code=zip_code,
            list_price=list_price,
            square_footage=square_footage,
            property_type=property_type,
            bedrooms=bedrooms,
            bathrooms=bathrooms
        )
        
        try:
            # Get value estimate - this gives us the market value (ARV)
            # Per Rentcast docs: "The value estimate returned by this endpoint 
            # represents the current market value, or after-repair value (ARV)"
            avm_result = self.client.get_value_estimate(
                address=address,
                property_type=property_type,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                square_footage=square_footage,
                max_radius=self.avm_max_radius,
                days_old=self.avm_days_old,
                comp_count=self.avm_comp_count
            )
            
            # Best Offer Price: Use the lower range of the AVM estimate
            # This represents a conservative offer price
            # We want best offer to not be too close to list price
            best_offer_price = avm_result.price_range_low
            
            # If best offer is too close to list price (within 5%), use lower bound
            if best_offer_price > list_price * 0.95:
                best_offer_price = avm_result.price_range_low * 0.9
            
            analysis.best_offer_price = best_offer_price
            analysis.best_offer_comparables = self._format_comparable_addresses(
                avm_result.comparables
            )
            
            # Calculate costs
            build_up, financing, all_inclusive = self._calculate_costs(
                best_offer_price, square_footage
            )
            analysis.build_up_cost = build_up
            analysis.financing_cost = financing
            analysis.all_inclusive_cost = all_inclusive
            
            # Upside Value: The AVM price represents the after-repair value
            # This is what the property would sell for after renovation
            analysis.upside_value = avm_result.price_range_high
            analysis.upside_comparables = self._format_comparable_addresses(
                avm_result.comparables
            )
            
            # Calculate profit and decision
            analysis.upside_profit = analysis.upside_value - analysis.all_inclusive_cost
            analysis.decision = "Yes" if analysis.upside_profit > self.upside_threshold else "No"
            
            logger.info(
                f"Analyzed {address}: "
                f"List=${list_price:,.0f}, "
                f"Offer=${best_offer_price:,.0f}, "
                f"ARV=${analysis.upside_value:,.0f}, "
                f"Profit=${analysis.upside_profit:,.0f}, "
                f"Decision={analysis.decision}"
            )
            
        except RentcastAPIError as e:
            logger.error(f"Failed to analyze {address}: {e}")
            analysis.error_message = str(e)
        
        return analysis
    
    def generate_report(
        self,
        zip_codes: list[str],
        property_types: Optional[list[str]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_sqft: Optional[int] = None,
        max_sqft: Optional[int] = None,
        status: str = "Active",
        limit: int = 500
    ) -> list[PropertyAnalysis]:
        """
        Generate a complete property investment report.
        
        This fetches all matching listings and analyzes each one,
        returning results sorted by upside profit (descending).
        
        Args:
            zip_codes: List of zip codes to search.
            property_types: List of property types to filter (e.g., ["Single Family", "Townhouse"]).
            min_price: Minimum listing price.
            max_price: Maximum listing price.
            min_sqft: Minimum square footage.
            max_sqft: Maximum square footage.
            status: Listing status filter.
            limit: Maximum number of listings to fetch per zip code (default 500).
            
        Returns:
            List of PropertyAnalysis objects sorted by upside_profit descending.
        """
        all_analyses = []
        
        # If no property types specified, use None to fetch all types
        if not property_types:
            property_types = [None]
        
        for zip_code in zip_codes:
            # Pass all property types in a single call
            property_type_param = ",".join(filter(None, property_types)) if property_types and property_types != [None] else None
            type_label = property_type_param or "All Types"
            logger.info(f"Processing zip code: {zip_code}, property types: {type_label}")
            
            try:
                # Fetch all matching listings for this zip code with all property types
                listings = self.client.get_sale_listings(
                    zip_code=zip_code,
                    property_type=property_type_param,
                    min_price=min_price,
                    max_price=max_price,
                    min_sqft=min_sqft,
                    max_sqft=max_sqft,
                    status=status,
                    limit=limit
                )
                
                logger.info(f"Found {len(listings)} listings in {zip_code} ({type_label})")
                
                # Analyze each property
                for listing in listings:
                    analysis = self._analyze_property(listing)
                    all_analyses.append(analysis)
                    
            except RentcastAPIError as e:
                logger.error(f"Failed to fetch listings for {zip_code} ({type_label}): {e}")
        
        # Sort by upside profit (descending) - best deals first
        all_analyses.sort(key=lambda x: x.upside_profit, reverse=True)
        
        logger.info(f"Completed analysis of {len(all_analyses)} properties")
        return all_analyses
