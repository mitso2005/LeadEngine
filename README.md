# LeadEngine API

A FastAPI-based lead enrichment service that leverages Apollo.io to discover and enrich company and contact information for Australian financial services technology leaders.

## Features

- **Company Enrichment** - Automatically fetch company data from Apollo.io
- **People Search** - Find technology leaders by title and location
- **Contact Enrichment** - Reveal emails and phone numbers via Apollo API
- **Smart Caching** - Database-backed caching prevents redundant API calls
- **Webhook Integration** - Phone numbers delivered asynchronously via Power Automate webhook

## Quick Start

### Prerequisites

- Python 3.9+
- Apollo.io API key
- Power Automate webhook URL (optional, for phone numbers)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd LeadEngine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Create a `.env` file:

```env
APOLLO_API_KEY=your_apollo_api_key_here
WEBHOOK_URL=your_power_automate_webhook_url_here
```

### Run the API

```bash
fastapi dev api/main.py
```

Access the interactive API docs at: `http://localhost:8000/docs`

## API Endpoints

### GET /enrich/custom

Enrich specific companies with custom search criteria.

**Parameters:**
- `domains` (string, required) - Comma-separated company domains
- `titles` (string, required) - Comma-separated job titles to search
- `max_results` (integer, optional) - Max people per company (default: 10)

**Example:**
```
GET /enrich/custom?domains=judo.bank,prospa.com&titles=CTO,VP Engineering&max_results=20
```

### POST /enrich/default

Run enrichment on all companies in database using default IT leadership titles.

**Example:**
```
POST /enrich/default
```

### GET /people

Retrieve all people from the database.

**Response:**
```json
{
  "count": 150,
  "people": [...]
}
```

### GET /companies

Retrieve all companies from the database.

**Response:**
```json
{
  "count": 50,
  "companies": [...]
}
```

### GET /stats

Get database statistics.

**Response:**
```json
{
  "total_companies": 50,
  "enriched_companies": 48,
  "total_people": 150,
  "enriched_people": 142
}
```

## Architecture

- **FastAPI** - Modern async web framework
- **SQLite** - Local database with WAL mode for concurrent access
- **Apollo.io API** - Lead data source
- **Power Automate** - Webhook receiver for phone numbers
- **Thread-safe** - Background webhook monitor for async phone delivery

## Caching Strategy

The API implements intelligent caching to minimize Apollo API usage:

1. **Company Enrichment** - Only enriches companies where `enriched = FALSE`
2. **People Search** - Only searches companies where `people_searched = FALSE`
3. **Contact Enrichment** - Only enriches people where `enriched = FALSE`

## Webhook Integration

Phone numbers are delivered asynchronously:

1. API calls Apollo with `reveal_phone_number=true` and webhook URL
2. Apollo sends phone data to Power Automate webhook
3. Power Automate saves JSON to `webhook_endpoint_data/` folder
4. Webhook monitor detects files and updates database
5. API waits for completion before returning results

### Run Standalone Script

```bash
python main.py
```

## License

Proprietary - RGF Staffing ANZ

## Support

For questions or issues, contact the digital transformations team.
