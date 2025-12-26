"""
Email Service Module

This module handles composing and sending HTML email reports
with property analysis data.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

from .report_generator import PropertyAnalysis

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Custom exception for email service errors."""
    pass


class EmailService:
    """
    Service for sending HTML email reports.
    
    Composes property analysis data into a formatted HTML email
    and sends it via SMTP.
    """
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        recipient_emails: list[str]
    ):
        """
        Initialize the email service.
        
        Args:
            smtp_server: SMTP server hostname.
            smtp_port: SMTP server port.
            sender_email: Email address to send from.
            sender_password: Password or app password for sender.
            recipient_emails: List of recipient email addresses.
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipient_emails = recipient_emails
    
    def _format_currency(self, value: float) -> str:
        """Format a number as USD currency."""
        return f"${value:,.0f}"
    
    def _format_comparables(self, comparables: list[str]) -> str:
        """Format a list of comparable addresses as HTML."""
        if not comparables:
            return "N/A"
        return "<br>".join(f"• {addr}" for addr in comparables)
    
    def _get_decision_style(self, decision: str) -> str:
        """Get CSS style for decision cell based on value."""
        if decision == "Yes":
            return "background-color: #d4edda; color: #155724; font-weight: bold;"
        return "background-color: #f8d7da; color: #721c24;"
    
    def _get_profit_style(self, profit: float) -> str:
        """Get CSS style for profit cell based on value."""
        if profit > 50000:
            return "background-color: #d4edda; color: #155724; font-weight: bold;"
        elif profit > 30000:
            return "background-color: #fff3cd; color: #856404;"
        elif profit > 0:
            return "color: #155724;"
        return "background-color: #f8d7da; color: #721c24;"
    
    def compose_html_report(
        self,
        analyses: list[PropertyAnalysis],
        report_date: Optional[datetime] = None
    ) -> str:
        """
        Compose an HTML email body with the property analysis report.
        
        Args:
            analyses: List of PropertyAnalysis objects to include.
            report_date: Date for the report header.
            
        Returns:
            HTML string containing the formatted report.
        """
        if report_date is None:
            report_date = datetime.now()
        
        date_str = report_date.strftime("%B %d, %Y")
        
        # Count decisions
        yes_count = sum(1 for a in analyses if a.decision == "Yes")
        no_count = len(analyses) - yes_count
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
            margin: 0 auto;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .summary {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 25px;
        }}
        .summary-item {{
            display: inline-block;
            margin-right: 30px;
            font-size: 16px;
        }}
        .summary-label {{
            font-weight: bold;
            color: #7f8c8d;
        }}
        .summary-value {{
            font-size: 20px;
            font-weight: bold;
        }}
        .yes-count {{ color: #27ae60; }}
        .no-count {{ color: #e74c3c; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 13px;
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid #ddd;
            vertical-align: top;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        .address-cell {{
            font-weight: bold;
            min-width: 200px;
        }}
        .price-cell {{
            text-align: right;
            white-space: nowrap;
        }}
        .comparables-cell {{
            font-size: 11px;
            color: #666;
            max-width: 250px;
        }}
        .decision-cell {{
            text-align: center;
            font-weight: bold;
        }}
        .error-row {{
            background-color: #ffeaa7 !important;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #7f8c8d;
            text-align: center;
        }}
        .legend {{
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
            font-size: 12px;
        }}
        .legend-title {{
            font-weight: bold;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Daily Property Investment Report</h1>
        <p><strong>Report Date:</strong> {date_str}</p>
        
        <div class="summary">
            <div class="summary-item">
                <span class="summary-label">Total Properties:</span>
                <span class="summary-value">{len(analyses)}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Recommended (Yes):</span>
                <span class="summary-value yes-count">{yes_count}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Not Recommended (No):</span>
                <span class="summary-value no-count">{no_count}</span>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Property Address</th>
                    <th>List Price</th>
                    <th>Best Offer Price</th>
                    <th>Best Offer Comparables</th>
                    <th>All Inclusive Cost (ARV)</th>
                    <th>Upside Value</th>
                    <th>Upside Comparables</th>
                    <th>Upside Profit</th>
                    <th>Decision</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for idx, analysis in enumerate(analyses, 1):
            error_class = "error-row" if analysis.error_message else ""
            decision_style = self._get_decision_style(analysis.decision)
            profit_style = self._get_profit_style(analysis.upside_profit)
            
            best_offer_comps = self._format_comparables(analysis.best_offer_comparables)
            upside_comps = self._format_comparables(analysis.upside_comparables)
            
            # Calculate cost breakdown for tooltip
            cost_breakdown = (
                f"Build Up: {self._format_currency(analysis.build_up_cost)} | "
                f"Financing: {self._format_currency(analysis.financing_cost)}"
            )
            
            html += f"""
                <tr class="{error_class}">
                    <td>{idx}</td>
                    <td class="address-cell">{analysis.address}</td>
                    <td class="price-cell">{self._format_currency(analysis.list_price)}</td>
                    <td class="price-cell">{self._format_currency(analysis.best_offer_price)}</td>
                    <td class="comparables-cell">{best_offer_comps}</td>
                    <td class="price-cell" title="{cost_breakdown}">
                        {self._format_currency(analysis.all_inclusive_cost)}
                        <br><small style="color: #888;">({cost_breakdown})</small>
                    </td>
                    <td class="price-cell">{self._format_currency(analysis.upside_value)}</td>
                    <td class="comparables-cell">{upside_comps}</td>
                    <td class="price-cell" style="{profit_style}">{self._format_currency(analysis.upside_profit)}</td>
                    <td class="decision-cell" style="{decision_style}">{analysis.decision}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
        
        <div class="legend">
            <div class="legend-title">📝 Report Calculations:</div>
            <ul>
                <li><strong>Best Offer Price:</strong> Conservative value estimate from comparable sold properties within 1 mile radius (last 12 months)</li>
                <li><strong>Build Up Cost:</strong> $75 per square foot for renovation</li>
                <li><strong>Financing Cost:</strong> 12% of (Best Offer Price + Build Up Cost)</li>
                <li><strong>All Inclusive Cost (ARV):</strong> Best Offer Price + Build Up Cost + Financing Cost</li>
                <li><strong>Upside Value:</strong> After-repair value based on renovated comparable properties</li>
                <li><strong>Upside Profit:</strong> Upside Value - All Inclusive Cost</li>
                <li><strong>Decision:</strong> "Yes" if Upside Profit > $30,000, otherwise "No"</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>This report was automatically generated using Rentcast API data.</p>
            <p>Properties are sorted by Upside Profit (highest first).</p>
            <p>Generated at: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def send_report(
        self,
        analyses: list[PropertyAnalysis],
        subject: Optional[str] = None
    ) -> bool:
        """
        Send the property report via email.
        
        Args:
            analyses: List of PropertyAnalysis objects to include.
            subject: Email subject line.
            
        Returns:
            True if email was sent successfully.
            
        Raises:
            EmailServiceError: If sending fails.
        """
        if subject is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            subject = f"Daily Property Investment Report - {date_str}"
        
        # Compose the HTML report
        html_content = self.compose_html_report(analyses)
        
        # Create the email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = ", ".join(self.recipient_emails)
        
        # Create plain text version (fallback)
        plain_text = f"""
Daily Property Investment Report

Total Properties Analyzed: {len(analyses)}
Recommended Properties: {sum(1 for a in analyses if a.decision == 'Yes')}

Please view this email in an HTML-capable email client for the full report.
"""
        
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        try:
            logger.info(f"Connecting to SMTP server {self.smtp_server}:{self.smtp_port}")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                
                server.sendmail(
                    self.sender_email,
                    self.recipient_emails,
                    msg.as_string()
                )
            
            logger.info(f"Report sent successfully to {self.recipient_emails}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {e}"
            logger.error(error_msg)
            raise EmailServiceError(error_msg) from e
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error occurred: {e}"
            logger.error(error_msg)
            raise EmailServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to send email: {e}"
            logger.error(error_msg)
            raise EmailServiceError(error_msg) from e
    
    def save_report_to_file(
        self,
        analyses: list[PropertyAnalysis],
        filepath: str
    ) -> None:
        """
        Save the HTML report to a file (for testing/debugging).
        
        Args:
            analyses: List of PropertyAnalysis objects.
            filepath: Path to save the HTML file.
        """
        html_content = self.compose_html_report(analyses)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Report saved to {filepath}")
