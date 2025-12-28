"""
Property Report Generator Module

This module generates investment property reports by analyzing
properties for sale and calculating potential investment returns.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .rentcast_client import RentcastClient, RentcastAPIError
from .config_manager import ZipCodeConfig

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
        comp_price_threshold: float = 500000.0,
        avm_max_radius: float = 1.0,
        avm_days_old: int = 365,
        avm_comp_count: int = 10,
        max_api_calls: int = 50
    ):
        """
        Initialize the report generator.
        
        Args:
            rentcast_client: Configured Rentcast API client.
            build_up_cost_per_sqft: Cost per square foot for renovation.
            financing_rate: Financing cost as a percentage (e.g., 0.12 = 12%).
            upside_threshold: Minimum profit threshold for "Yes" decision.
            comp_price_threshold: Maximum comp price threshold for filtering.
            avm_max_radius: Maximum radius for AVM comparables (miles).
            avm_days_old: Maximum age of AVM comparables (days).
            avm_comp_count: Number of AVM comparables to fetch.
            max_api_calls: Maximum number of API calls allowed per run.
        """
        self.client = rentcast_client
        self.build_up_cost_per_sqft = build_up_cost_per_sqft
        self.financing_rate = financing_rate
        self.upside_threshold = upside_threshold
        self.comp_price_threshold = comp_price_threshold
        self.avm_max_radius = avm_max_radius
        self.avm_days_old = avm_days_old
        self.avm_comp_count = avm_comp_count
        self.max_api_calls = max_api_calls
    
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
        addresses = []
        for comp in comparables[:5]:  # Limit to top 5 for brevity
            # Handle both listing format and property record format
            addr = comp.get("formattedAddress") or comp.get("addressLine1", "Unknown")
            price = comp.get("price") or comp.get("lastSalePrice", 0)
            if price:
                addr = f"{addr} (${price:,.0f})"
            addresses.append(addr)
        return addresses
    
    def _filter_and_analyze_comps(
        self,
        sold_properties: list,
        subject_list_price: float,
        subject_sqft: int
    ) -> tuple[float, float, list]:
        """
        Filter sold properties and extract min/max prices for upside analysis.
        
        Filters to keep only properties with price >= 1.5x subject list price
        AND price <= comp_price_threshold (from config).
        Then returns the lowest and highest prices from the filtered list.
        
        Args:
            sold_properties: List of sold property records.
            subject_list_price: The subject property's list price.
            subject_sqft: The subject property's square footage.
            
        Returns:
            Tuple of (min_price, max_price, filtered_comparables).
        """
        # Filter range: 1.5x subject list price to comp_price_threshold
        min_allowed_price = subject_list_price * 1.5
        max_allowed_price = self.comp_price_threshold
        
        # Filter properties and extract prices
        filtered_comps = []
        for prop in sold_properties:
            # Get the sale price from property record
            sale_price = prop.get("lastSalePrice", 0)
            
            # Keep comps with price >= 1.5x list price AND <= threshold
            if sale_price and sale_price >= min_allowed_price and sale_price <= max_allowed_price:
                filtered_comps.append({
                    "formattedAddress": prop.get("formattedAddress") or prop.get("addressLine1", ""),
                    "price": sale_price,
                    "squareFootage": prop.get("squareFootage", 0),
                    "bedrooms": prop.get("bedrooms"),
                    "bathrooms": prop.get("bathrooms"),
                    "lastSaleDate": prop.get("lastSaleDate", "")
                })
        
        if not filtered_comps:
            logger.warning(
                f"No comparable sold properties found after filtering "
                f"(range: ${min_allowed_price:,.0f} - ${max_allowed_price:,.0f})"
            )
            return 0, 0, []
        
        # Sort by price to get min and max
        filtered_comps.sort(key=lambda x: x["price"])
        
        min_price = filtered_comps[0]["price"]
        max_price = filtered_comps[-1]["price"]
        
        logger.info(
            f"Filtered {len(filtered_comps)} comps from {len(sold_properties)} sold properties. "
            f"Filter range: ${min_allowed_price:,.0f} - ${max_allowed_price:,.0f}, "
            f"Result range: ${min_price:,.0f} - ${max_price:,.0f}"
        )
        
        return min_price, max_price, filtered_comps
    
    def _analyze_property(self, listing: dict, property_types: Optional[list[str]] = None) -> PropertyAnalysis:
        """
        Perform complete investment analysis on a single property.
        
        This fetches sold comparable properties within 1 mile radius,
        filters them, and uses the min/max prices for upside analysis.
        
        Args:
            listing: Property listing dictionary from the Sale Listings API.
            property_types: List of property types to use for comp search (from config).
            
        Returns:
            PropertyAnalysis with all calculated metrics.
        """
        address = listing.get("formattedAddress", "")
        zip_code = listing.get("zipCode", "")
        list_price = listing.get("price", 0)
        square_footage = listing.get("squareFootage", 0) or 1000  # Default if missing
        property_type = listing.get("propertyType", "Single Family")
        bedrooms = listing.get("bedrooms") or 3  # Default if missing
        bathrooms = listing.get("bathrooms") or 2  # Default if missing
        latitude = listing.get("latitude")
        longitude = listing.get("longitude")
        
        analysis = PropertyAnalysis(
            address=address,
            zip_code=zip_code,
            list_price=list_price,
            square_footage=square_footage,
            property_type=property_type,
            bedrooms=bedrooms,
            bathrooms=bathrooms
        )
        
        # Check if we have coordinates for radius search
        if not latitude or not longitude:
            logger.warning(f"No coordinates for {address}, skipping analysis")
            analysis.error_message = "No coordinates available for property"
            return analysis
        
        try:
            # Build property type parameter for sold properties search
            # Use property_types from config if provided, otherwise use subject property type
            if property_types and len(property_types) > 0:
                property_type_param = "|".join(property_types)  # API uses | for multiple values
            else:
                property_type_param = property_type
            
            # Fetch sold properties within 1 mile radius
            # Filters:
            # - Sale date: last 6 months (180 days)
            # - Bedrooms: subject bedrooms to 5
            # - Bathrooms: subject bathrooms to 4
            # - Square footage: subject sqft - 200 to subject sqft + 400
            sold_properties = self.client.get_sold_properties(
                latitude=latitude,
                longitude=longitude,
                radius=self.avm_max_radius,  # 1 mile default
                sale_date_range_days=self.avm_days_old,  # 180 days = 6 months
                bedrooms_min=bedrooms,
                bedrooms_max=5,
                bathrooms_min=bathrooms,
                bathrooms_max=4,
                sqft_min=square_footage - 200,
                sqft_max=square_footage + 400,
                property_type=property_type_param,
                limit=self.avm_comp_count
            )
            
            if not sold_properties:
                logger.warning(f"No sold properties found for {address}")
                analysis.error_message = "No comparable sold properties found"
                return analysis
            
            # Filter comps (exclude price > 1.5x list price) and get min/max
            min_comp_price, max_comp_price, filtered_comps = self._filter_and_analyze_comps(
                sold_properties, list_price, square_footage
            )
            
            if not filtered_comps:
                logger.warning(f"All comps filtered out for {address}")
                analysis.error_message = "No valid comparable properties after filtering"
                return analysis
            
            # Best Offer Price: Keep as subject property list price
            best_offer_price = list_price
            analysis.best_offer_price = best_offer_price
            analysis.best_offer_comparables = self._format_comparable_addresses(filtered_comps)
            
            # Calculate costs based on best offer price
            build_up, financing, all_inclusive = self._calculate_costs(
                best_offer_price, square_footage
            )
            analysis.build_up_cost = build_up
            analysis.financing_cost = financing
            analysis.all_inclusive_cost = all_inclusive
            
            # Upside Value: Use max price from filtered comps (highest upside)
            analysis.upside_value = max_comp_price
            analysis.upside_comparables = self._format_comparable_addresses(filtered_comps)
            
            # Calculate profit using min comp price (conservative/minimum upside)
            # Minimum upside profit = lowest comp price - all inclusive cost
            min_upside_profit = min_comp_price - all_inclusive
            # Maximum upside profit = highest comp price - all inclusive cost
            max_upside_profit = max_comp_price - all_inclusive
            
            # Use minimum upside profit for decision (conservative approach)
            analysis.upside_profit = max_upside_profit
            
            # Decision: Yes if MINIMUM upside profit > threshold
            analysis.decision = "Yes" if max_upside_profit > self.upside_threshold else "No"
            
            logger.info(
                f"Analyzed {address}: "
                f"List=${list_price:,.0f}, "
                f"Offer=${best_offer_price:,.0f}, "
                f"Min Comp=${min_comp_price:,.0f}, "
                f"Max Comp=${max_comp_price:,.0f}, "
                f"All-In=${all_inclusive:,.0f}, "
                f"Min Profit=${min_upside_profit:,.0f}, "
                f"Max Profit=${max_upside_profit:,.0f}, "
                f"Decision={analysis.decision}"
            )
            
        except RentcastAPIError as e:
            logger.error(f"Failed to analyze {address}: {e}")
            analysis.error_message = str(e)
        
        return analysis
    
    def generate_report(
        self,
        zip_codes: list[ZipCodeConfig],
        property_types: Optional[list[str]] = None,
        status: str = "Active",
        limit: int = 500
    ) -> list[PropertyAnalysis]:
        """
        Generate a complete property investment report.
        
        This fetches all matching listings and analyzes each one,
        returning results sorted by upside profit (descending).
        
        Args:
            zip_codes: List of ZipCodeConfig objects with zip-specific filters.
            property_types: List of property types to filter (e.g., ["Single Family", "Townhouse"]).
            status: Listing status filter.
            limit: Maximum number of listings to fetch per zip code (default 500).
            
        Returns:
            List of PropertyAnalysis objects sorted by upside_profit descending.
            
        Raises:
            SystemExit: If estimated API calls exceed max_api_calls threshold.
        """
        # If no property types specified, use None to fetch all types
        if not property_types:
            property_types = [None]
        
        # Phase 1: Fetch all listings first to calculate API call count
        all_listings = []  # List of (listing, zip_config, property_types) tuples
        distinct_zip_codes = set()
        
        logger.info("=" * 50)
        logger.info("Phase 1: Fetching listings to estimate API calls...")
        logger.info("=" * 50)
        
        for zip_config in zip_codes:
            zip_code = zip_config.zip_code
            distinct_zip_codes.add(zip_code)
            
            # Pass all property types in a single call
            property_type_param = ",".join(filter(None, property_types)) if property_types and property_types != [None] else None
            type_label = property_type_param or "All Types"
            logger.info(
                f"Fetching listings for zip code: {zip_code}, property types: {type_label}, "
                f"price: ${zip_config.min_price or 0:,.0f}-${zip_config.max_price or 999999999:,.0f}, "
                f"sqft: {zip_config.min_sqft or 0}-{zip_config.max_sqft or 999999}"
            )
            
            try:
                # Fetch all matching listings for this zip code with zip-specific filters
                listings = self.client.get_sale_listings(
                    zip_code=zip_code,
                    property_type=property_type_param,
                    min_price=zip_config.min_price,
                    max_price=zip_config.max_price,
                    min_sqft=zip_config.min_sqft,
                    max_sqft=zip_config.max_sqft,
                    status=status,
                    limit=limit
                )
                
                # Sort listings by price (ascending order - lowest price first)
                listings.sort(key=lambda x: x.get("price", 0), reverse=False)
                
                logger.info(f"Found {len(listings)} listings in {zip_code} ({type_label})")
                
                # Store listings with their context for later analysis
                for listing in listings:
                    all_listings.append((listing, zip_config, property_types if property_types != [None] else None))
                    
            except RentcastAPIError as e:
                logger.error(f"Failed to fetch listings for {zip_code} ({type_label}): {e}")
        
        # Phase 2: Calculate and check API call count
        # API calls = zip code fetches (already done) + 1 per listing (for sold comps)
        zip_code_api_calls = len(distinct_zip_codes)
        listing_api_calls = len(all_listings)
        total_api_calls = zip_code_api_calls + listing_api_calls
        
        logger.info("=" * 50)
        logger.info("API Call Estimate:")
        logger.info(f"  Distinct zip codes: {zip_code_api_calls}")
        logger.info(f"  Listings to analyze: {listing_api_calls}")
        logger.info(f"  Total API calls: {total_api_calls}")
        logger.info(f"  Maximum allowed: {self.max_api_calls}")
        logger.info("=" * 50)
        
        if total_api_calls > self.max_api_calls:
            logger.error(
                f"API call limit exceeded! Estimated {total_api_calls} calls, "
                f"but maximum allowed is {self.max_api_calls}. "
                f"Reduce the number of zip codes or tighten filters to reduce listings."
            )
            raise SystemExit(
                f"API call limit exceeded: {total_api_calls} > {self.max_api_calls}. "
                f"Adjust filters to reduce listings count."
            )
        
        logger.info(f"API call check passed. Proceeding with analysis...")
        
        # Phase 3: Analyze each property
        logger.info("=" * 50)
        logger.info("Phase 2: Analyzing properties...")
        logger.info("=" * 50)
        
        all_analyses = []
        for listing, zip_config, prop_types in all_listings:
            analysis = self._analyze_property(listing, property_types=prop_types)
            all_analyses.append(analysis)
        
        # Sort by upside profit (descending) - best deals first
        all_analyses.sort(key=lambda x: x.upside_profit, reverse=True)
        
        logger.info(f"Completed analysis of {len(all_analyses)} properties")
        return all_analyses
