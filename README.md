# Security group inbound rule IP address updater

## Circumstance
You're doing development on a remote computer, say, an EC2 instance. You use SSH or similar to access the remote. You'd like to restrict SSH access to your remote to accept connections
from only one IP address, the external IP address of your local computer.  But your external address changes frequently (like you're doing this work while on an airplane.)

If the remote computer is an EC2 instance, then you've set up an inbound rule to restrict SSH connections to just the external IP address of your local computer.  But when your external IP address changes, you now have to get back into your AWS console and update the inbound rule with the new IP address.

What you'd like is some process that monitors the external IP address of your local computer and automatically updates the inbound rule in your remote computer with the new IP address for the port(s) you need to access.  That is the whole purpose of this project.


# sg_ip_monitor

Monitors your external IP address every 30 seconds and automatically updates
an AWS EC2 security group inbound rule when a change is detected.

Useful when travelling on long-haul flights where in-flight Wi-Fi allocates a
new public IP mid-flight, locking you out of your EC2 instance.

The script only ever touches inbound rules it created itself (identified by a
description tag), so any rules you have manually added are never modified or
removed.

---

## Requirements

- **Python 3.10 or later** — the script uses the `X | Y` union type syntax
  introduced in Python 3.10. Earlier versions will raise a `SyntaxError` at
  startup.
- An AWS account with an EC2 security group you want to keep updated.
- The AWS CLI installed on your machine
  ([installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)).

---

## Step 1 — Create an IAM Policy

The script needs three EC2 permissions and nothing else. Creating the policy
first means you can attach it immediately when you create the user.

1. Sign in to the [AWS IAM console](https://console.aws.amazon.com/iam/).
2. In the left sidebar click **Policies**, then **Create policy**.
3. Click the **JSON** tab and replace the contents with:

```json
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

4. Click **Next**.
5. Give the policy the name `sg-ip-monitor-policy` and an optional
   description such as *Allows sg_ip_monitor to update EC2 inbound rules*.
6. Click **Create policy**.

---

## Step 2 — Create an IAM User

1. In the IAM console left sidebar click **Users**, then **Create user**.
2. Enter a username such as `sg-ip-monitor`.
3. **Do not** check *Provide user access to the AWS Management Console* — this
   identity only needs API access.
4. Click **Next**.
5. On the *Set permissions* screen choose **Attach policies directly**.
6. Search for `sg-ip-monitor-policy`, check the box next to it, and click
   **Next**.
7. Click **Create user**.

### Generate and download credentials

8. Click into the newly created user, then open the **Security credentials**
   tab.
9. Scroll to **Access keys** and click **Create access key**.
10. For *Use case* select **Command Line Interface (CLI)**, acknowledge the
    notice, and click **Next**.
11. Click **Create access key**.
12. Click **Download .csv file** and save it somewhere safe — the secret key
    is only shown once. The CSV contains two columns: `Access key ID` and
    `Secret access key`.

---

## Step 3 — Configure the AWS CLI Profile

Import the downloaded CSV file directly into a named AWS CLI profile so you
never have to paste keys manually.

```bash
aws configure import --csv file:///path/to/credentials.csv
```

The profile name is taken from the *User name* column in the CSV, which AWS
sets to the IAM username (`sg-ip-monitor`).

Verify the import succeeded:

```bash
aws configure list --profile sg-ip-monitor
```

Expected output:

```
      Name                    Value             Type    Location
      ----                    -----             ----    --------
   profile             sg-ip-monitor           manual    --profile
access_key     ****************XXXX shared-credentials-file
secret_key     ****************XXXX shared-credentials-file
    region             eu-central-1      config-file    ~/.aws/config
```

Tell the script to use this profile by setting the environment variable below
(you can add it to the same block as the other variables in Step 4):

```bash
export AWS_PROFILE=sg-ip-monitor
```

---

## Step 4 — Set Environment Variables

The script reads its configuration from environment variables. Set them in
your shell before running, or add them to your shell's startup file
(`~/.bashrc`, `~/.zshrc`, etc.).

### Required

| Variable | Description | Example |
|---|---|---|
| `SG_ID` | The ID of the security group to update | `sg-0abc123def456789` |
| `AWS_REGION` | AWS region where the security group lives | `eu-central-1` |
| `AWS_PROFILE` | The CLI profile created in Step 3 | `sg-ip-monitor` |

```bash
export SG_ID="sg-0abc123def456789"
export AWS_REGION="eu-central-1"
export AWS_PROFILE="sg-ip-monitor"
```

Find your security group ID in the AWS console under
**EC2 → Network & Security → Security Groups**.

### Optional

| Variable | Default | Description |
|---|---|---|
| `SG_PORTS` | `22` | Comma-separated list of ports to manage, e.g. `22,8080` |
| `SG_PROTOCOL` | `tcp` | IP protocol for the inbound rules |
| `SG_RULE_DESC` | `sg-ip-monitor: auto-updated` | Description tag used to identify managed rules |
| `CHECK_INTERVAL` | `30` | How often to check for an IP change, in seconds |

```bash
# Example: manage SSH and a custom port, check every 60 seconds
export SG_PORTS="22,8080"
export CHECK_INTERVAL="60"
```

---

## Step 5 — Create a Project Folder and Clone the Repo

```bash
mkdir ~/sg-ip-monitor
cd ~/sg-ip-monitor
git clone https://github.com/YOUR_USERNAME/sg_ip_monitor.git .
```

---

## Step 6 — Create and Activate a Virtual Environment

> Requires Python 3.10 or later. Check your version with `python3 --version`.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt will change to show `(.venv)` when the environment is active.

---

## Step 7 — Install Dependencies

```bash
pip install boto3 requests
```

---

## Step 8 — Run the Script

With the virtual environment active and environment variables set:

```bash
python sg_ip_monitor.py
```

### Expected output — startup

```
2026-05-26 14:02:11  INFO     ════════════════════════════════════════════════════════════
2026-05-26 14:02:11  INFO     sg_ip_monitor starting
2026-05-26 14:02:11  INFO       Security group : sg-0abc123def456789
2026-05-26 14:02:11  INFO       Region         : eu-central-1
2026-05-26 14:02:11  INFO       Ports          : [22]
2026-05-26 14:02:11  INFO       Check interval : 30s
2026-05-26 14:02:11  INFO     ════════════════════════════════════════════════════════════
2026-05-26 14:02:12  INFO     Initial IP detected: 203.0.113.47
2026-05-26 14:02:12  INFO     Updating security group sg-0abc123def456789 …
2026-05-26 14:02:12  INFO       Authorized port 22     203.0.113.47/32
2026-05-26 14:02:12  INFO     Security group updated successfully.
```

### Expected output — when the IP changes mid-flight

```
2026-05-26 15:34:07  INFO     IP changed: 203.0.113.47 → 198.51.100.22
2026-05-26 15:34:07  INFO     Updating security group sg-0abc123def456789 …
2026-05-26 15:34:08  INFO       Revoked  port 22     203.0.113.47/32
2026-05-26 15:34:08  INFO       Authorized port 22     198.51.100.22/32
2026-05-26 15:34:08  INFO     Security group updated successfully.
```

### Expected output — when the IP is unchanged

No output is printed during stable periods. The script checks silently every
30 seconds (or whatever `CHECK_INTERVAL` is set to) and only logs when
something changes.

Stop the script at any time with **Ctrl-C**:

```
2026-05-26 15:40:00  INFO     Stopped by user.
```

---

## Running as a Background Process

To keep the script running after you close your terminal, or to run it
unattended while you work, use `nohup` combined with `&`.

```bash
nohup python sg_ip_monitor.py > sg_ip_monitor.log 2>&1 &
```

- `nohup` — prevents the process from being killed when the terminal closes
- `> sg_ip_monitor.log` — redirects stdout to a log file
- `2>&1` — redirects stderr into the same log file
- `&` — runs the process in the background

The shell will print the process ID (PID), for example:

```
[1] 48271
```

**Tail the log** to watch it in real time:

```bash
tail -f sg_ip_monitor.log
```

**Stop the background process** when you no longer need it:

```bash
kill 48271
```

If you have forgotten the PID:

```bash
pgrep -a -f sg_ip_monitor.py
```

---

## Troubleshooting

**`SyntaxError` on startup** — your Python version is older than 3.10. Run
`python3 --version` and upgrade if needed.

**`Security group ID not set`** — the `SG_ID` environment variable is missing.
Make sure you exported it in the same shell session (or terminal tab) where
you are running the script.

**`Could not describe security group`** — the AWS profile or region is wrong,
or the IAM policy is not attached. Run
`aws ec2 describe-security-groups --group-ids $SG_ID --profile sg-ip-monitor`
to test access independently.

**`All IP services failed`** — the machine has no internet connection. The
script will keep retrying every cycle and recover automatically once
connectivity is restored.




