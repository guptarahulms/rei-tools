#!/usr/bin/env python3
"""
Daily Property Report Generator

This is the main entry point for generating and sending daily
property investment reports using the Rentcast API.

Usage:
    python main.py [--config CONFIG_PATH] [--dry-run] [--save-html PATH]

Options:
    --config PATH    Path to the configuration file (default: config.ini)
    --dry-run        Generate report without sending email
    --save-html PATH Save the HTML report to a file
    --verbose        Enable verbose logging
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from property_report import (
    ConfigManager,
    ConfigurationError,
    RentcastClient,
    RentcastAPIError,
    ReportGenerator,
    EmailService,
    EmailServiceError,
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate and send daily property investment reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to the configuration file (default: config.ini in package directory)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate report without sending email"
    )
    
    parser.add_argument(
        "--save-html",
        type=str,
        default=None,
        help="Save the HTML report to a file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the property report generator.
    
    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    args = parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Daily Property Investment Report Generator")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config_manager = ConfigManager(args.config)
        config = config_manager.get_app_config()
        
        logger.info(f"Zip codes to search: {config.filters.zip_codes}")
        logger.info(f"Property types: {config.filters.property_types}")
        logger.info(f"Price range: ${config.filters.min_price:,.0f} - ${config.filters.max_price:,.0f}")
        logger.info(f"Square footage: {config.filters.min_sqft} - {config.filters.max_sqft} sq ft")
        
        # Initialize Rentcast client
        logger.info("Initializing Rentcast API client...")
        rentcast_client = RentcastClient(
            api_key=config.rentcast.api_key,
            base_url=config.rentcast.base_url
        )
        
        # Initialize report generator
        report_generator = ReportGenerator(
            rentcast_client=rentcast_client,
            build_up_cost_per_sqft=config.costs.build_up_cost_per_sqft,
            financing_rate=config.costs.financing_rate,
            upside_threshold=config.decision.upside_threshold,
            avm_max_radius=config.avm.max_radius,
            avm_days_old=config.avm.days_old,
            avm_comp_count=config.avm.comp_count
        )
        
        # Generate the report
        logger.info("Generating property report...")
        analyses = report_generator.generate_report(
            zip_codes=config.filters.zip_codes,
            property_types=config.filters.property_types,
            min_price=config.filters.min_price,
            max_price=config.filters.max_price,
            min_sqft=config.filters.min_sqft,
            max_sqft=config.filters.max_sqft,
            status=config.filters.status,
            limit=config.filters.limit
        )
        
        if not analyses:
            logger.warning("No properties found matching the criteria.")
            return 0
        
        # Summary statistics
        yes_count = sum(1 for a in analyses if a.decision == "Yes")
        no_count = len(analyses) - yes_count
        total_upside = sum(a.upside_profit for a in analyses if a.upside_profit > 0)
        
        logger.info("-" * 40)
        logger.info("Report Summary:")
        logger.info(f"  Total properties analyzed: {len(analyses)}")
        logger.info(f"  Recommended (Yes): {yes_count}")
        logger.info(f"  Not recommended (No): {no_count}")
        logger.info(f"  Total potential upside: ${total_upside:,.0f}")
        logger.info("-" * 40)
        
        # Initialize email service
        email_service = EmailService(
            smtp_server=config.email.smtp_server,
            smtp_port=config.email.smtp_port,
            sender_email=config.email.sender_email,
            sender_password=config.email.sender_password,
            recipient_emails=config.email.recipient_emails
        )
        
        # Save HTML report if requested
        if args.save_html:
            logger.info(f"Saving HTML report to: {args.save_html}")
            email_service.save_report_to_file(analyses, args.save_html)
        
        # Send email unless dry run
        if args.dry_run:
            logger.info("Dry run mode - skipping email send")
            # In dry run, save to a default file if not already saved
            if not args.save_html:
                default_html = f"property_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                logger.info(f"Saving HTML report to: {default_html}")
                email_service.save_report_to_file(analyses, default_html)
        else:
            logger.info(f"Sending report to: {config.email.recipient_emails}")
            email_service.send_report(analyses, subject=config.email.subject)
            logger.info("Report sent successfully!")
        
        logger.info("=" * 60)
        logger.info("Report generation completed successfully!")
        logger.info("=" * 60)
        return 0
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except RentcastAPIError as e:
        logger.error(f"Rentcast API error: {e}")
        return 2
    except EmailServiceError as e:
        logger.error(f"Email service error: {e}")
        return 3
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 99


if __name__ == "__main__":
    sys.exit(main())
