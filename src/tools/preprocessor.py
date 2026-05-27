import json
import boto3
import os
import urllib.parse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")

s3_client = boto3.client("s3", region_name=AWS_REGION)

# =========================
# SEVERITY SCORING
# =========================

SEVERITY_SCORE = {
    "CRITICAL": 4,
    "MAJOR":    3,
    "MINOR":    2,
    "WARNING":  1,
    "UNKNOWN":  0,
}

CRITICALITY_SCORE = {
    "CRITICAL": 3,
    "HIGH":     2,
    "MEDIUM":   1,
    "LOW":      0,
}

# =========================
# ENRICHMENT
# =========================

def enrich_alarm(alarm):
    """Add derived fields useful for the agent."""

    # Priority score — combines severity + node criticality
    severity_score = SEVERITY_SCORE.get(alarm.get("severity", "UNKNOWN"), 0)
    criticality_score = CRITICALITY_SCORE.get(alarm.get("criticality", "LOW"), 0)
    alarm["priority_score"] = severity_score + criticality_score

    # Flag if this alarm is part of a known incident
    alarm["is_incident"] = not alarm.get("incident_id", "").startswith("NOISE")

    # Flag high impact — more than 5000 users affected
    alarm["high_impact"] = alarm.get("affected_users", 0) >= 5000

    # Human readable summary for the agent to reason over
    alarm["agent_summary"] = build_agent_summary(alarm)

    # Processing metadata
    alarm["processed_at"] = datetime.utcnow().isoformat() + "Z"

    return alarm

def build_agent_summary(alarm):
    """One-line summary the agent can use directly in reasoning."""
    return (
        f"[{alarm.get('severity','?')}] {alarm.get('alarm_type','?')} "
        f"on {alarm.get('node_id','?')} ({alarm.get('node_type','?')}) "
        f"at {alarm.get('site','?')} — "
        f"{alarm.get('affected_users',0)} users affected — "
        f"status: {alarm.get('status','?')}"
    )

# =========================
# DEDUPLICATION
# =========================

def deduplicate(alarms):
    """
    Remove duplicate alarms — same node + alarm_type within 5 minutes
    Keep the highest severity one.
    """
    seen = {}
    for alarm in alarms:
        key = (alarm.get("node_id"), alarm.get("alarm_type"))
        if key not in seen:
            seen[key] = alarm
        else:
            existing_score = SEVERITY_SCORE.get(seen[key].get("severity"), 0)
            new_score = SEVERITY_SCORE.get(alarm.get("severity"), 0)
            if new_score > existing_score:
                seen[key] = alarm
    return list(seen.values())

# =========================
# INCIDENT GROUPING
# =========================

def group_by_incident(alarms):
    """Group alarms by incident_id for agent context."""
    incidents = {}
    for alarm in alarms:
        inc_id = alarm.get("incident_id", "UNKNOWN")
        if inc_id not in incidents:
            incidents[inc_id] = []
        incidents[inc_id].append(alarm)
    return incidents

# =========================
# MAIN PROCESSING
# =========================

def process_batch(raw_alarms):
    """Full processing pipeline for a batch of alarms."""

    print(f"Processing {len(raw_alarms)} raw alarms...")

    # Step 1 — enrich each alarm
    enriched = [enrich_alarm(alarm) for alarm in raw_alarms]

    # Step 2 — deduplicate
    deduplicated = deduplicate(enriched)
    print(f"After deduplication: {len(deduplicated)} alarms")

    # Step 3 — sort by priority score descending
    deduplicated.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

    # Step 4 — group by incident
    incidents = group_by_incident(deduplicated)
    print(f"Grouped into {len(incidents)} incidents")

    return {
        "processed_alarms": deduplicated,
        "incidents":        incidents,
        "summary": {
            "total_raw":       len(raw_alarms),
            "total_processed": len(deduplicated),
            "total_incidents": len(incidents),
            "critical_count":  sum(1 for a in deduplicated if a.get("severity") == "CRITICAL"),
            "high_impact_count": sum(1 for a in deduplicated if a.get("high_impact")),
            "processed_at":    datetime.utcnow().isoformat() + "Z",
        }
    }

# =========================
# S3 HELPERS
# =========================

def read_from_s3(bucket, key):
    """Read a JSON file from S3."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))

def write_to_s3(bucket, key, data):
    """Write processed data back to S3."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, indent=2),
        ContentType="application/json",
    )
    print(f"Written to s3://{bucket}/{key}")

# =========================
# LAMBDA HANDLER
# =========================

def lambda_handler(event, context):
    """
    Entry point for AWS Lambda.
    Triggered by EventBridge when a new file lands in raw-alarms/
    """
    print(f"Event received: {json.dumps(event)}")

    try:
        # Extract bucket and key from the S3 event
        record = event["detail"]
        bucket = record["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["object"]["key"])

        print(f"Processing file: s3://{bucket}/{key}")

        # Read raw alarms from S3
        raw_alarms = read_from_s3(bucket, key)

        # Process
        result = process_batch(raw_alarms)

        # Write processed output to S3
        processed_key = key.replace("raw-alarms/", "processed/")
        write_to_s3(bucket, processed_key, result)

        return {
            "statusCode": 200,
            "body": json.dumps(result["summary"])
        }

    except Exception as e:
        print(f"Error processing event: {str(e)}")
        raise

# =========================
# LOCAL TEST RUNNER
# =========================

if __name__ == "__main__":
    """Run locally against the latest file in S3 for testing."""
    import sys

    print("Listing raw-alarms/ in S3...")
    response = s3_client.list_objects_v2(
        Bucket=S3_BUCKET,
        Prefix="raw-alarms/"
    )

    if "Contents" not in response:
        print("No files found in raw-alarms/ — run alarm_simulator.py first")
        sys.exit(1)

    # Get the most recent file
    files = sorted(response["Contents"], key=lambda x: x["LastModified"], reverse=True)
    latest_key = files[0]["Key"]
    print(f"Processing: {latest_key}")

    raw_alarms = read_from_s3(S3_BUCKET, latest_key)
    result = process_batch(raw_alarms)

    processed_key = latest_key.replace("raw-alarms/", "processed/")
    write_to_s3(S3_BUCKET, processed_key, result)

    print("\nSummary:")
    print(json.dumps(result["summary"], indent=2))

    print("\nTop 3 priority alarms:")
    for alarm in result["processed_alarms"][:3]:
        print(f"  {alarm['agent_summary']}")