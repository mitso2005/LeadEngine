# Webhook Setup for Phone Numbers

## Quick Setup (2 minutes)

### Step 1: Get Your Webhook URL
1. Go to **https://webhook.site** in your browser
2. You'll immediately see a unique URL like: `https://webhook.site/12345678-abcd-1234-5678-1234567890ab`
3. **Copy this URL** - you'll need it in Step 2

### Step 2: Configure the Code
Open `main.py` and find line ~11:
```python
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://webhook.site/unique-id-here")
```

Replace `"https://webhook.site/unique-id-here"` with your actual webhook.site URL:
```python
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://webhook.site/12345678-abcd-1234-5678-1234567890ab")
```

### Step 3: Run the Code
```bash
python3 main.py
```

### Step 4: Receive Phone Numbers
- The script will complete and show emails immediately
- **Phone numbers arrive 2-5 minutes later** at your webhook.site URL
- Go back to the webhook.site tab and refresh - you'll see the phone data arrive!

## Understanding the Webhook Response

When phone numbers arrive, you'll receive JSON data like:
```json
{
  "status": "success",
  "people": [
    {
      "id": "587cf802f65125cad923a266",
      "phone_numbers": [
        {
          "raw_number": "+61 2 1234 5678",
          "sanitized_number": "+61212345678",
          "type": "mobile"
        }
      ]
    }
  ]
}
```

## What Happens
1. ✅ **Emails** - returned immediately in API response, saved to CSV
2. ⏰ **Phone numbers** - sent to webhook 2-5 minutes later
3. 📊 **Credits** - Each person enrichment costs credits (emails + phones)

## Production Setup (Later)
For production, you'll want to:
1. Build a webhook endpoint that receives the phone data
2. Automatically updates your database/CSV when phone numbers arrive
3. Deploy to a permanent URL (not webhook.site which expires)

But for testing/dev, webhook.site is perfect!
