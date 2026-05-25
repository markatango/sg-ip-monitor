# Security group inbound rule IP address updater

## Circumstance
You're doing development on a remote computer, say, an EC2 instance. You use SSH or similar to access the remote. You'd like to restrict SSH access to your remote to accept connections
from only one IP address, the external IP address of your local computer.  But your external address changes frequently (like you're doing this work while on an airplane.)

If the remote computer is an EC2 instance, then you've set up an inbound rule to restrict SSH connections to just the external IP address of your local computer.  But when your external IP address changes, you now have to get back into your AWS console and update the inbound rule with the new IP address.

What you'd like is some process that monitors the external IP address of your local computer and automatically updates the inbound rule in your remote computer with the new IP address for the port(s) you need to access.  That is the whole purpose of this project.

## Pre-installation
AWS actions
- Log into aws console as root or as a user with full aws console authority.
- Set up a new IAM user in your AWS account.  DO NOT enable console access for this user.
- Create an api keypair for this user and download the keypair in a .csv file.
- Create a policy and attach it to the new user
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ManageSecurityGroupRules",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeSecurityGroups",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupIngress"
            ],
            "Resource": "*"
        }
    ]
}
```

Local computer actions:
- Install and configure awscli

```
$ sudo apt install awscli
```
- Log in to aws and create a profile for the new IAM user.
```
$ aws login
$ aws configure --profile <new user name> import --csv <path to credential file for new user>
```

Set up these environment variables on your local computer:

- AWS_REGION="YOUR_PREFERRED_AWS_REGION"  (e.g., "us-east-1")
- SG_ID="sg-YOUR_SECURITY_GROUP"   
- SG_PORTS=22  (alternatively, [port1, port2, ...])
- SG_PROTOCOL="tcp"  (or "udp" depending on how you use the specified port(s))
- SG_RULE_DESC="sg-ip-monitor: auto-updated"  (The new rule will have this name to distinguish it from any other manually added rule)
- CHECK_INTERVAL=30  (Update interval in seconds)

Create a directory for this project and enter it.

```
$ mkdir new_directory
$ cd new_directory
```

Create a new environment and activate it.

```
$ python -m venv venv
$ source venv/bin/activate
```

## Installation

`$ git clone github.com/markatango/sg-ip-monitor.git`

## Operation

`$ python sg-ip-monitor.py`

or

`$ nohup python sg-ip-monitor.py &`  if you want this to run in the background.

Typical output:

```
2026-05-25 17:31:11  INFO      ════════════════════════════════════════════════════════════
2026-05-25 17:31:11  INFO      sg_ip_monitor starting
2026-05-25 17:31:11  INFO        Security group : sg-26c4d543
2026-05-25 17:31:11  INFO        Region         : us-east-1
2026-05-25 17:31:11  INFO        Ports          : [22]
2026-05-25 17:31:11  INFO        Check interval : 30s
2026-05-25 17:31:11  INFO      ════════════════════════════════════════════════════════════
2026-05-25 17:31:11  INFO      Initial IP detected: 145.224.75.128
2026-05-25 17:31:11  INFO      Updating security group sg-26c4d543 …
2026-05-25 17:31:11  INFO      Found credentials in shared credentials file: ~/.aws/credentials
2026-05-25 17:31:18  INFO        Revoked  port 22      145.224.74.153/32
2026-05-25 17:31:18  INFO        Authorized port 22     145.224.75.128/32
2026-05-25 17:31:18  INFO      Security group updated successfully.
```


