#!/usr/bin/env python3
"""
sg_ip_monitor.py

Monitors your external IP address every 30 seconds.
When a change is detected, automatically updates an AWS EC2
security group inbound rule to allow access from the new IP.

Configuration: edit the CONFIG block below, or set environment variables.

Requirements:
    pip install boto3 requests

AWS credentials must be available via one of:
  - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  - ~/.aws/credentials file
  - IAM instance profile (if running on EC2)

Required IAM permissions:
  - ec2:DescribeSecurityGroups
  - ec2:AuthorizeSecurityGroupIngress
  - ec2:RevokeSecurityGroupIngress
"""

import time
import logging
import os
import sys
import requests
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

CONFIG = {
    # AWS region where your security group lives
    "aws_region": os.environ.get("AWS_REGION", "us-east-1"),

    # Your security group ID, e.g. "sg-0abc123def456789"
    "security_group_id": os.environ.get("SG_ID", "sg-26c4d543"),

    # Comma-separated list of ports to keep updated, e.g. "22,8080"
    # All ports listed will have their rules updated to the new IP.
    "ports": [int(p) for p in os.environ.get("SG_PORTS", "22").split(",")],

    # Protocol for the inbound rules
    "protocol": os.environ.get("SG_PROTOCOL", "tcp"),

    # Optional: description tag on the inbound rule so we can find it again.
    # All managed rules get this description.
    "rule_description": os.environ.get("SG_RULE_DESC", "sg-ip-monitor: auto-updated"),

    # IAM profile to use when editing security group
    "aws_profile": os.environ.get("AWS_PROFILE", "sg-ip-monitor"),

    # How often to check (seconds)
    "check_interval": int(os.environ.get("CHECK_INTERVAL", "30")),

    # IP-check services tried in order; first success wins
    "ip_services": [
        "https://api4.my-ip.io/ip",
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
        "https://icanhazip.com",
    ],

    # Timeout for IP-check HTTP requests (seconds)
    "ip_request_timeout": 10,
}

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── IP DETECTION ─────────────────────────────────────────────────────────────

def get_external_ip() -> str | None:
    """Try each IP-check service in turn; return the first clean result."""
    for url in CONFIG["ip_services"]:
        try:
            resp = requests.get(url, timeout=CONFIG["ip_request_timeout"])
            resp.raise_for_status()
            ip = resp.text.strip()
            if ip:
#                print(ip)
                return ip
        except requests.RequestException as exc:
            log.debug("IP service %s failed: %s", url, exc)
    log.warning("All IP services failed; will retry next cycle.")
    return None

# ─── SECURITY GROUP HELPERS ───────────────────────────────────────────────────

def get_ec2_client():
    session = boto3.Session(profile_name=CONFIG["aws_profile"])
    return session.client("ec2", region_name=CONFIG["aws_region"])

def describe_sg(ec2, sg_id: str) -> dict:
    resp = ec2.describe_security_groups(GroupIds=[sg_id])
    return resp["SecurityGroups"][0]


def find_managed_rules(sg: dict, port: int) -> list[dict]:
    """
    Return existing inbound rules on `port` whose description matches
    our managed tag (so we never accidentally touch hand-crafted rules).
    """
    managed = []
    for perm in sg.get("IpPermissions", []):
        if (
            perm.get("IpProtocol") == CONFIG["protocol"]
            and perm.get("FromPort") == port
            and perm.get("ToPort") == port
        ):
            for r in perm.get("IpRanges", []):
                if r.get("Description") == CONFIG["rule_description"]:
                    managed.append({
                        "port": port,
                        "cidr": r["CidrIp"],
                        "description": r.get("Description", ""),
                    })
    return managed


def revoke_rule(ec2, sg_id: str, port: int, cidr: str) -> None:
    ec2.revoke_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": CONFIG["protocol"],
            "FromPort": port,
            "ToPort": port,
            "IpRanges": [{"CidrIp": cidr, "Description": CONFIG["rule_description"]}],
        }],
    )
    log.info("  Revoked  port %-6s  %s", port, cidr)


def authorize_rule(ec2, sg_id: str, port: int, cidr: str) -> None:
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": CONFIG["protocol"],
            "FromPort": port,
            "ToPort": port,
            "IpRanges": [{"CidrIp": cidr, "Description": CONFIG["rule_description"]}],
        }],
    )
    log.info("  Authorized port %-5s  %s", port, cidr)


def update_security_group(new_ip: str) -> bool:
    """
    For every port in CONFIG['ports']:
      1. Revoke any existing managed rules.
      2. Add a new rule for new_ip/32.
    Returns True on full success, False if any port failed.
    """
    new_cidr = f"{new_ip}/32"
    ec2 = get_ec2_client()
    sg_id = CONFIG["security_group_id"]
    success = True

    try:
        sg = describe_sg(ec2, sg_id)
    except (BotoCoreError, ClientError) as exc:
        log.error("Could not describe security group %s: %s", sg_id, exc)
        return False

    for port in CONFIG["ports"]:
        try:
            old_rules = find_managed_rules(sg, port)
            for rule in old_rules:
                if rule["cidr"] == new_cidr:
                    log.info("Port %s already allows %s — nothing to do.", port, new_cidr)
                    break
                revoke_rule(ec2, sg_id, port, rule["cidr"])
            else:
                authorize_rule(ec2, sg_id, port, new_cidr)
        except (BotoCoreError, ClientError) as exc:
            log.error("Failed to update port %s: %s", port, exc)
            success = False

    return success

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

def main() -> None:
    sg_id = CONFIG["security_group_id"]
    if sg_id == "sg-CHANGEME":
        log.error(
            "Security group ID not set. "
            "Edit CONFIG['security_group_id'] or set the SG_ID environment variable."
        )
        sys.exit(1)

    log.info("═" * 60)
    log.info("sg_ip_monitor starting")
    log.info("  Security group : %s", sg_id)
    log.info("  Region         : %s", CONFIG["aws_region"])
    log.info("  Ports          : %s", CONFIG["ports"])
    log.info("  Check interval : %ss", CONFIG["check_interval"])
    log.info("═" * 60)

    current_ip: str | None = None

    while True:
        new_ip = get_external_ip()

        if new_ip is None:
            # Couldn't reach any IP service; wait and retry
            time.sleep(CONFIG["check_interval"])
            continue

        if new_ip == current_ip:
            log.debug("IP unchanged: %s", current_ip)
        else:
            if current_ip is None:
                log.info("Initial IP detected: %s", new_ip)
            else:
                log.info("IP changed: %s → %s", current_ip, new_ip)

            log.info("Updating security group %s …", sg_id)
            if update_security_group(new_ip):
                current_ip = new_ip
                log.info("Security group updated successfully.")
            else:
                log.warning(
                    "Security group update had errors. "
                    "Will retry on next cycle."
                )

        time.sleep(CONFIG["check_interval"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped by user.")
