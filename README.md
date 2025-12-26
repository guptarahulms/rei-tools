# REI Tools - Property Investment Report Generator

A Python tool that generates daily property investment reports using the Rentcast API and sends them via email.

## Features

- **Automated Property Search**: Fetches active sale listings from Rentcast API based on configurable criteria (zip code, price range, property type, square footage)
- **Investment Analysis**: Calculates key investment metrics for each property:
  - Best Offer Price (from comparable sales)
  - Build Up Cost (renovation cost based on square footage)
  - Financing Cost (12% of acquisition + renovation)
  - All Inclusive Cost (total investment)
  - Upside Value (after-repair value)
  - Decision recommendation (Yes/No based on profit threshold)
- **HTML Email Reports**: Beautiful, mobile-friendly HTML reports embedded in email
- **Cost Optimization**: Minimizes API calls to reduce costs

## Installation

1. Clone or download this repository
2. Install dependencies:

```bash
cd rei-tools
pip install -r requirements.txt
```

Or using pip with the project:

```bash
pip install .
```

## Configuration

Edit the `property_report/config.ini` file with your settings:

### Rentcast API Settings
```ini
[rentcast]
api_key = YOUR_API_KEY_HERE
base_url = https://api.rentcast.io/v1
```

### Property Filters
```ini
[filters]
zip_codes = 19146,19131,19138  # Comma-separated zip codes
property_type = Single Family   # Single Family, Condo, Townhouse, Multi-Family
min_price = 100000
max_price = 500000
min_sqft = 1000
max_sqft = 3000
status = Active
```

### Cost Parameters
```ini
[costs]
build_up_cost_per_sqft = 75    # $/sqft for renovation
financing_rate = 0.12          # 12% financing cost
```

### Decision Criteria
```ini
[decision]
upside_threshold = 30000       # Minimum profit for "Yes" decision
```

### Email Settings
```ini
[email]
smtp_server = smtp.gmail.com
smtp_port = 587
sender_email = your_email@gmail.com
sender_password = your_app_password
recipient_emails = recipient1@example.com,recipient2@example.com
subject = Daily Property Investment Report
```

> **Note**: For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

## Usage

### Basic Usage (Generate and Send Report)
```bash
python main.py
```

### Dry Run (Generate without sending email)
```bash
python main.py --dry-run
```

### Save HTML Report to File
```bash
python main.py --save-html report.html --dry-run
```

### Custom Configuration File
```bash
python main.py --config /path/to/custom_config.ini
```

### Verbose Logging
```bash
python main.py --verbose
```

## Report Columns

| Column | Description |
|--------|-------------|
| Property Address | Full street address with zip code |
| List Price | Current asking price |
| Best Offer Price | Conservative offer based on comparable sales (lower range of AVM) |
| Best Offer Comparables | Properties used to determine best offer |
| All Inclusive Cost (ARV) | Best Offer + Build Up Cost + Financing Cost |
| Upside Value | After-repair value based on renovated comparables |
| Upside Comparables | Properties used for upside valuation |
| Upside Profit | Upside Value - All Inclusive Cost |
| Decision | Yes if profit > $30K, otherwise No |

## Calculation Logic

1. **Best Offer Price**: Lower bound of the AVM estimate from Rentcast, representing a conservative purchase price

2. **Build Up Cost**: `$75 × Square Footage` (configurable)

3. **Financing Cost**: `12% × (Best Offer Price + Build Up Cost)`

4. **All Inclusive Cost**: `Best Offer Price + Build Up Cost + Financing Cost`

5. **Upside Value**: Market value (ARV) from Rentcast AVM endpoint, based on comparable sold properties within 1 mile radius in the last 12 months

6. **Upside Profit**: `Upside Value - All Inclusive Cost`

7. **Decision**: 
   - **Yes**: If `Upside Profit > $30,000`
   - **No**: Otherwise

## API Call Optimization

To minimize API costs, the tool:
- Makes **1 call** to fetch all listings per zip code (Sale Listings endpoint)
- Makes **1 call** per property for valuation (AVM endpoint returns both current value and ARV)

## Scheduling Daily Reports

### Windows Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to daily at desired time
4. Action: Start a program
5. Program: `python`
6. Arguments: `C:\path\to\rei-tools\main.py`

### Linux/Mac Cron
```bash
# Run daily at 8 AM
0 8 * * * cd /path/to/rei-tools && python main.py
```

## Project Structure

```
rei-tools/
├── main.py                     # Entry point
├── pyproject.toml              # Project configuration
├── requirements.txt            # Dependencies
├── README.md                   # This file
└── property_report/
    ├── __init__.py             # Package initialization
    ├── config.ini              # Configuration file
    ├── config_manager.py       # Configuration parser
    ├── rentcast_client.py      # Rentcast API client
    ├── report_generator.py     # Report generation logic
    └── email_service.py        # Email composition and sending
```

## Error Handling

The tool handles various error scenarios:
- **Configuration errors**: Missing or invalid configuration values
- **API errors**: Network issues, authentication failures, rate limits
- **Email errors**: SMTP authentication, connection issues

All errors are logged with detailed messages for troubleshooting.

## License

MIT License

## Support

For Rentcast API documentation, visit: https://developers.rentcast.io/
