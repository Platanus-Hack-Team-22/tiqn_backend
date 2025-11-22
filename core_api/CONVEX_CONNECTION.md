# Convex Database Connection

## ✅ Connected to Production

Your Python backend is now connected to the production Convex database:

```
Deployment: knowing-mouse-775
URL: https://knowing-mouse-775.convex.cloud
```

## How It Works

Your team member manages the Convex schema and functions in the cloud. Your Python code simply calls those functions via the Convex client.

### Python Integration

The `src/services/convex_db.py` service handles all Convex interactions:

```python
from src.services.convex_db import get_convex_service

# Get the service (uses CONVEX_URL from environment)
convex = get_convex_service()

# Call Convex mutations (creates records)
result = convex.save_emergency_call(
    session_id="call-123",
    full_transcript="...",
    canonical_data=canonical,
    duration_seconds=125.4,
    chunk_count=25,
    dispatcher_id="<dispatcher-id>"
)

# Call Convex queries (reads data)
incident = convex.get_incident(incident_id)
recent = convex.list_recent_incidents(limit=10)
```

## Environment Variables

Your `.envrc` is configured:

```bash
export CONVEX_URL=https://knowing-mouse-775.convex.cloud
export CONVEX_DEPLOYMENT=knowing-mouse-775
```

After any changes to `.envrc`, reload with:
```bash
direnv allow
```

## Required Convex Functions

Your Python code expects these functions to exist in Convex Cloud:

### Mutations (Create/Update)
- `patients:create` - Create patient record
- `incidents:create` - Create incident record
- `calls:create` - Create call record
- `system:now` - Get server timestamp

### Queries (Read)
- `incidents:get` - Get incident by ID
- `incidents:listRecent` - List recent incidents
- `patients:get` - Get patient by ID

**Note:** Your team member should have these deployed in the cloud. If any are missing, coordinate with them to add them.

## Testing Connection

Test your connection:

```python
from convex import ConvexClient
import os

client = ConvexClient(os.getenv("CONVEX_URL"))

# Test query (requires function to exist in Convex)
try:
    result = client.query("incidents:listRecent", {"limit": 5})
    print(f"✅ Connected! Found {len(result)} incidents")
except Exception as e:
    print(f"❌ Error: {e}")
    print("Check that required functions exist in Convex Cloud")
```

## Dashboard

View your data at:
**https://dashboard.convex.dev/t/github-e41c9/knowing-mouse-775**

## Schema Location

The schema is managed in your Convex Cloud deployment, not in this repository. To see or modify the schema, check with your team member or view it in the Convex Dashboard.

## Data Flow

```
Your Python Code
    ↓ (calls via convex client)
Convex Cloud (knowing-mouse-775)
    ↓ (stores in)
Database Tables: patients, incidents, calls, etc.
```

## Troubleshooting

### "Failed to connect"
Check that `CONVEX_URL` is set:
```bash
echo $CONVEX_URL
# Should show: https://knowing-mouse-775.convex.cloud
```

### "Function not found"
The required Convex function doesn't exist in the cloud deployment. Coordinate with your team member to deploy it.

### "Invalid arguments"
The function exists but expects different arguments. Check the schema in Convex Dashboard.

## Summary

✅ Connected to production: `knowing-mouse-775`  
✅ Python service ready: `src/services/convex_db.py`  
✅ No local schema needed - managed in cloud  
✅ Ready to save emergency call data  

