import json
import random
import uuid
import boto3
import os
from datetime import datetime, timedelta
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

fake = Faker()

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)

NODES = [
    {"id": "NODE-LTE-001", "type": "eNodeB",   "site": "Cairo-North", "vendor": "Ericsson"},
    {"id": "NODE-LTE-002", "type": "eNodeB",   "site": "Cairo-South", "vendor": "Ericsson"},
    {"id": "NODE-LTE-003", "type": "eNodeB",   "site": "Alex-East",   "vendor": "Nokia"},
    {"id": "NODE-GPON-001","type": "OLT",       "site": "Cairo-North", "vendor": "Huawei"},
    {"id": "NODE-GPON-002","type": "OLT",       "site": "Cairo-South", "vendor": "Huawei"},
    {"id": "NODE-CORE-001","type": "MME",       "site": "Core-DC",     "vendor": "Ericsson"},
    {"id": "NODE-CORE-002","type": "SGW",       "site": "Core-DC",     "vendor": "Ericsson"},
    {"id": "NODE-MW-001",  "type": "Microwave", "site": "Alex-West",   "vendor": "Nokia"},
]

ALARM_TYPES = [
    {"name": "LINK_DOWN",          "severity": "CRITICAL", "affected": ["eNodeB", "OLT", "Microwave"]},
    {"name": "HIGH_BER",           "severity": "MAJOR",    "affected": ["eNodeB", "Microwave"]},
    {"name": "PACKET_LOSS",        "severity": "MAJOR",    "affected": ["eNodeB", "OLT", "MME"]},
    {"name": "HIGH_CPU",           "severity": "MINOR",    "affected": ["MME", "SGW", "OLT"]},
    {"name": "HIGH_LATENCY",       "severity": "MAJOR",    "affected": ["MME", "SGW", "eNodeB"]},
    {"name": "POWER_FAILURE",      "severity": "CRITICAL", "affected": ["eNodeB", "Microwave", "OLT"]},
    {"name": "TEMPERATURE_HIGH",   "severity": "MINOR",    "affected": ["eNodeB", "OLT"]},
    {"name": "SYNC_LOSS",          "severity": "CRITICAL", "affected": ["eNodeB", "Microwave"]},
    {"name": "CAPACITY_THRESHOLD", "severity": "MINOR",    "affected": ["MME", "SGW"]},
    {"name": "INTERFACE_FLAPPING", "severity": "MAJOR",    "affected": ["eNodeB", "OLT", "Microwave"]},
]

def generate_kpis(alarm_type):
    base = {
        "cpu_utilization":    round(random.uniform(10, 40), 1),
        "memory_utilization": round(random.uniform(20, 50), 1),
        "packet_loss_pct":    round(random.uniform(0, 0.5), 2),
        "latency_ms":         round(random.uniform(5, 20), 1),
        "ber":                round(random.uniform(0, 0.001), 5),
        "temperature_c":      round(random.uniform(20, 35), 1),
    }
    if alarm_type == "HIGH_CPU":
        base["cpu_utilization"] = round(random.uniform(85, 99), 1)
    elif alarm_type == "PACKET_LOSS":
        base["packet_loss_pct"] = round(random.uniform(5, 30), 2)
    elif alarm_type == "HIGH_LATENCY":
        base["latency_ms"] = round(random.uniform(150, 500), 1)
    elif alarm_type == "HIGH_BER":
        base["ber"] = round(random.uniform(0.01, 0.1), 5)
    elif alarm_type == "TEMPERATURE_HIGH":
        base["temperature_c"] = round(random.uniform(70, 95), 1)
    return base

def generate_description(node, alarm_type, kpis):
    descriptions = {
        "LINK_DOWN":          f"Physical link down on {node['id']} at site {node['site']}. No traffic passing.",
        "HIGH_BER":           f"Bit error rate {kpis['ber']} exceeds threshold on {node['id']}.",
        "PACKET_LOSS":        f"Packet loss {kpis['packet_loss_pct']}% on {node['id']}. Service impact likely.",
        "HIGH_CPU":           f"CPU utilization {kpis['cpu_utilization']}% on {node['id']}. Risk of process failure.",
        "HIGH_LATENCY":       f"Latency {kpis['latency_ms']}ms on {node['id']} exceeds SLA threshold.",
        "POWER_FAILURE":      f"Power supply failure on {node['id']} at {node['site']}. Running on backup.",
        "TEMPERATURE_HIGH":   f"Temperature {kpis['temperature_c']}C on {node['id']} exceeds safe limit.",
        "SYNC_LOSS":          f"Timing sync lost on {node['id']}. Cell may go out of service.",
        "CAPACITY_THRESHOLD": f"Capacity threshold breached on {node['id']}.",
        "INTERFACE_FLAPPING": f"Interface flapping on {node['id']}. Unstable physical connection.",
    }
    return descriptions.get(alarm_type, "Unknown alarm condition.")

def generate_alarm(timestamp=None):
    if timestamp is None:
        timestamp = datetime.utcnow()
    node = random.choice(NODES)
    valid_alarms = [a for a in ALARM_TYPES if node["type"] in a["affected"]]
    alarm_type = random.choice(valid_alarms)
    kpis = generate_kpis(alarm_type["name"])
    return {
        "alarm_id":   str(uuid.uuid4()),
        "timestamp":  timestamp.isoformat() + "Z",
        "node_id":    node["id"],
        "node_type":  node["type"],
        "site":       node["site"],
        "vendor":     node["vendor"],
        "alarm_type": alarm_type["name"],
        "severity":   alarm_type["severity"],
        "kpis":       kpis,
        "status":     "ACTIVE",
        "description": generate_description(node, alarm_type["name"], kpis)
    }

def generate_batch(n=10, hours_back=24):
    alarms = []
    now = datetime.utcnow()
    for _ in range(n):
        offset = random.uniform(0, hours_back * 3600)
        timestamp = now - timedelta(seconds=offset)
        alarms.append(generate_alarm(timestamp))
    alarms.sort(key=lambda x: x["timestamp"])
    return alarms

def upload_to_s3(alarms):
    """Upload alarm batch to S3 as a timestamped JSON file."""
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    key = f"raw-alarms/batch-{timestamp}.json"
    body = json.dumps(alarms, indent=2)

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json"
    )
    print(f"Uploaded {len(alarms)} alarms to s3://{S3_BUCKET}/{key}")
    return key

if __name__ == "__main__":
    alarms = generate_batch(n=50, hours_back=24)
    key = upload_to_s3(alarms)
    print(f"\nSample alarm:")
    print(json.dumps(alarms[0], indent=2))