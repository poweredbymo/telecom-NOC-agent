import json
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)

# =========================
# CASCADE PATTERNS
# Known patterns for root cause inference
# =========================

CASCADE_PATTERNS = {
    "POWER_FAILURE": {
        "likely_secondaries": ["LINK_DOWN", "PACKET_LOSS", "HIGH_LATENCY"],
        "explanation": "Power failure causes transport link loss which cascades to packet loss on dependent nodes."
    },
    "LINK_DOWN": {
        "likely_secondaries": ["PACKET_LOSS", "HIGH_LATENCY", "SYNC_LOSS"],
        "explanation": "Link failure causes traffic loss and timing reference loss on dependent nodes."
    },
    "HIGH_BER": {
        "likely_secondaries": ["PACKET_LOSS", "HIGH_LATENCY", "LINK_DOWN"],
        "explanation": "Signal degradation causes packet errors which escalate to link failure if uncorrected."
    },
    "SYNC_LOSS": {
        "likely_secondaries": ["INTERFACE_FLAPPING", "PACKET_LOSS"],
        "explanation": "Timing loss causes interface instability and traffic disruption."
    },
    "HIGH_CPU": {
        "likely_secondaries": ["HIGH_LATENCY", "PACKET_LOSS"],
        "explanation": "Processing overload causes delay and eventual packet loss."
    },
}

SEVERITY_ORDER = ["CRITICAL", "MAJOR", "MINOR", "WARNING", "UNKNOWN"]

# =========================
# CORE LOGIC
# =========================

def identify_root_cause(incident_alarms):
    """
    Given a list of alarms from the same incident,
    identify the most likely root cause.

    Logic:
    1. Sort by timestamp, earliest alarm is the first signal
    2. Prioritise by severity, CRITICAL alarms are likely root causes
    3. Check cascade patterns, does the earliest alarm explain the rest?
    4. Check topology, is the node a known upstream dependency?
    """

    if not incident_alarms:
        return None

    # Sort by timestamp ascending
    sorted_alarms = sorted(incident_alarms, key=lambda x: x.get("timestamp", ""))

    # Get the earliest alarm
    earliest = sorted_alarms[0]

    # Get all alarm types in this incident
    alarm_types_in_incident = set(a.get("alarm_type") for a in sorted_alarms)

