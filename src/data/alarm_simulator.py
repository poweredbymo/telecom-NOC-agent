import json
import random
import uuid
import boto3
import os

from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# =========================
# AWS CONFIG
# =========================

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)

# =========================
# NETWORK TOPOLOGY
# =========================

NODES = [
    {
        "id": "NODE-LTE-001",
        "type": "eNodeB",
        "site": "Cairo-North",
        "vendor": "Ericsson",
        "criticality": "HIGH",
        "affected_users": 3500,
    },
    {
        "id": "NODE-LTE-002",
        "type": "eNodeB",
        "site": "Cairo-South",
        "vendor": "Ericsson",
        "criticality": "HIGH",
        "affected_users": 2800,
    },
    {
        "id": "NODE-GPON-001",
        "type": "OLT",
        "site": "Cairo-North",
        "vendor": "Huawei",
        "criticality": "HIGH",
        "affected_users": 5000,
    },
    {
        "id": "NODE-MW-001",
        "type": "Microwave",
        "site": "Alex-West",
        "vendor": "Nokia",
        "criticality": "MEDIUM",
        "affected_users": 1200,
    },
    {
        "id": "NODE-CORE-001",
        "type": "MME",
        "site": "Core-DC",
        "vendor": "Ericsson",
        "criticality": "CRITICAL",
        "affected_users": 25000,
    },
]

# =========================
# TOPOLOGY RELATIONSHIPS
# =========================

DEPENDENCIES = {
    "NODE-MW-001": ["NODE-LTE-001"],
    "NODE-GPON-001": ["NODE-LTE-002"],
    "NODE-CORE-001": [
        "NODE-LTE-001",
        "NODE-LTE-002",
        "NODE-GPON-001",
    ],
}

# =========================
# ALARM DEFINITIONS
# =========================

ALARM_TYPES = {
    "LINK_DOWN": {
        "severity": "CRITICAL",
    },
    "HIGH_BER": {
        "severity": "MAJOR",
    },
    "PACKET_LOSS": {
        "severity": "MAJOR",
    },
    "HIGH_CPU": {
        "severity": "MINOR",
    },
    "HIGH_LATENCY": {
        "severity": "MAJOR",
    },
    "POWER_FAILURE": {
        "severity": "CRITICAL",
    },
    "SYNC_LOSS": {
        "severity": "CRITICAL",
    },
    "INTERFACE_FLAPPING": {
        "severity": "MAJOR",
    },
}

# =========================
# INCIDENT SCENARIOS
# =========================

SCENARIOS = {
    "POWER_FAILURE": [
        "POWER_FAILURE",
        "LINK_DOWN",
        "PACKET_LOSS",
        "HIGH_LATENCY",
    ],
    "MICROWAVE_DEGRADATION": [
        "HIGH_BER",
        "PACKET_LOSS",
        "HIGH_LATENCY",
        "LINK_DOWN",
    ],
    "CORE_CONGESTION": [
        "HIGH_CPU",
        "HIGH_LATENCY",
        "PACKET_LOSS",
    ],
    "INTERMITTENT_LINK": [
        "INTERFACE_FLAPPING",
        "PACKET_LOSS",
        "INTERFACE_FLAPPING",
    ],
}

# =========================
# KPI GENERATION
# =========================

def generate_kpis(alarm_type):

    base = {
        "cpu_utilization": round(random.uniform(15, 40), 1),
        "memory_utilization": round(random.uniform(25, 60), 1),
        "packet_loss_pct": round(random.uniform(0, 1), 2),
        "latency_ms": round(random.uniform(5, 20), 1),
        "ber": round(random.uniform(0, 0.001), 5),
        "temperature_c": round(random.uniform(22, 35), 1),
    }

    if alarm_type == "HIGH_CPU":
        base["cpu_utilization"] = round(random.uniform(85, 99), 1)

    elif alarm_type == "PACKET_LOSS":
        base["packet_loss_pct"] = round(random.uniform(5, 35), 2)

    elif alarm_type == "HIGH_LATENCY":
        base["latency_ms"] = round(random.uniform(150, 600), 1)

    elif alarm_type == "HIGH_BER":
        base["ber"] = round(random.uniform(0.01, 0.08), 5)

    elif alarm_type == "POWER_FAILURE":
        base["packet_loss_pct"] = 100
        base["latency_ms"] = 999

    return base

# =========================
# STATUS LIFECYCLE
# =========================

def generate_status():

    r = random.random()

    if r < 0.70:
        return "ACTIVE"

    elif r < 0.90:
        return "ACKNOWLEDGED"

    return "CLEARED"

# =========================
# DESCRIPTION GENERATOR
# =========================

def generate_description(node, alarm_type, kpis):

    descriptions = {
        "LINK_DOWN":
            f"Transport link failure detected on {node['id']} at {node['site']}.",

        "HIGH_BER":
            f"Microwave BER degradation detected on {node['id']} with BER={kpis['ber']}.",

        "PACKET_LOSS":
            f"Packet loss reached {kpis['packet_loss_pct']}% on {node['id']}.",

        "HIGH_CPU":
            f"CPU utilization reached {kpis['cpu_utilization']}% on {node['id']}.",

        "HIGH_LATENCY":
            f"Latency exceeded SLA threshold on {node['id']} ({kpis['latency_ms']}ms).",

        "POWER_FAILURE":
            f"Power subsystem failure detected on {node['id']} at site {node['site']}.",

        "SYNC_LOSS":
            f"Synchronization reference lost on {node['id']}.",

        "INTERFACE_FLAPPING":
            f"Unstable interface state detected on {node['id']}.",
    }

    return descriptions.get(alarm_type, "Unknown alarm.")

# =========================
# SINGLE ALARM CREATION
# =========================

def create_alarm(
    node,
    alarm_type,
    timestamp,
    incident_id,
    root_cause=None,
):

    kpis = generate_kpis(alarm_type)

    status = generate_status()

    cleared_timestamp = None

    if status == "CLEARED":
        cleared_timestamp = (
            timestamp + timedelta(minutes=random.randint(5, 120))
        ).isoformat() + "Z"

    return {
        "alarm_id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "timestamp": timestamp.isoformat() + "Z",
        "cleared_timestamp": cleared_timestamp,
        "status": status,
        "node_id": node["id"],
        "node_type": node["type"],
        "site": node["site"],
        "vendor": node["vendor"],
        "criticality": node["criticality"],
        "affected_users": node["affected_users"],
        "alarm_type": alarm_type,
        "severity": ALARM_TYPES[alarm_type]["severity"],
        "root_cause": root_cause,
        "kpis": kpis,
        "description": generate_description(node, alarm_type, kpis),
    }

# =========================
# INCIDENT GENERATION
# =========================

def generate_incident(base_time):

    scenario_name = random.choice(list(SCENARIOS.keys()))

    scenario = SCENARIOS[scenario_name]

    incident_id = f"INC-{random.randint(1000,9999)}"

    root_node = random.choice(NODES)

    alarms = []

    root_alarm = scenario[0]

    alarms.append(
        create_alarm(
            node=root_node,
            alarm_type=root_alarm,
            timestamp=base_time,
            incident_id=incident_id,
            root_cause=root_alarm,
        )
    )

    dependent_nodes = DEPENDENCIES.get(root_node["id"], [])

    for i, alarm_type in enumerate(scenario[1:], start=1):

        timestamp = base_time + timedelta(
            minutes=random.randint(i * 2, i * 5)
        )

        if dependent_nodes:
            node_id = random.choice(dependent_nodes)
            node = next(n for n in NODES if n["id"] == node_id)
        else:
            node = root_node

        alarms.append(
            create_alarm(
                node=node,
                alarm_type=alarm_type,
                timestamp=timestamp,
                incident_id=incident_id,
                root_cause=root_alarm,
            )
        )

    return alarms

# =========================
# BACKGROUND NOISE
# =========================

def generate_noise_alarm(timestamp):

    node = random.choice(NODES)

    alarm_type = random.choice(list(ALARM_TYPES.keys()))

    return create_alarm(
        node=node,
        alarm_type=alarm_type,
        timestamp=timestamp,
        incident_id=f"NOISE-{random.randint(10000,99999)}",
    )

# =========================
# BATCH GENERATION
# =========================

def generate_batch(
    incidents=5,
    noise_alarms=20,
    hours_back=24,
):

    alarms = []

    now = datetime.utcnow()

    # Generate incidents
    for _ in range(incidents):

        offset = random.uniform(0, hours_back * 3600)

        incident_time = now - timedelta(seconds=offset)

        alarms.extend(generate_incident(incident_time))

    # Generate background noise
    for _ in range(noise_alarms):

        offset = random.uniform(0, hours_back * 3600)

        timestamp = now - timedelta(seconds=offset)

        alarms.append(generate_noise_alarm(timestamp))

    alarms.sort(key=lambda x: x["timestamp"])

    return alarms

# =========================
# S3 UPLOAD
# =========================

def upload_to_s3(alarms):

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

    key = f"raw-alarms/batch-{timestamp}.json"

    body = json.dumps(alarms, indent=2)

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
    )

    print(f"Uploaded {len(alarms)} alarms to s3://{S3_BUCKET}/{key}")

    return key

# =========================
# MAIN
# =========================

if __name__ == "__main__":

    alarms = generate_batch(
        incidents=10,
        noise_alarms=30,
        hours_back=24,
    )

    upload_to_s3(alarms)

    print("\nSample alarm:\n")

    print(json.dumps(alarms[0], indent=2))