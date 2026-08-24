"""Start the Minecraft EC2 instance on demand.

Deployed as a Lambda behind a Function URL. A player opens the URL, the
instance starts, and the page tells them how long to wait.

Why this exists: the instance powers itself off when nobody is playing
(see aws/systemd/), which is what makes the whole thing cheap. Something
then has to turn it back on, and it cannot be the instance itself.

Auth is a shared secret in the query string. That is deliberately modest
security for a deliberately modest risk: the worst an attacker can do is
start a Minecraft server that would auto-stop again within 20 minutes.
It is not protecting data -- the instance is not reachable from here in
any other way. Do not extend this function to stop, terminate, or modify
anything without revisiting that reasoning.

Environment:
    INSTANCE_ID   -- the EC2 instance to start (required)
    WAKE_SECRET   -- shared secret; callers pass ?key=<secret> (required)
    BOOT_ESTIMATE -- minutes to show players (default "3")
"""

from __future__ import annotations

import hmac
import os

import boto3

ec2 = boto3.client("ec2")

# Instance states that mean "already on the way up"; starting again is a
# harmless no-op but reporting it accurately avoids confusing players.
LIVE_STATES = {"pending", "running"}


def _page(title: str, detail: str, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": (
            "<!doctype html><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:32rem;"
            "margin:4rem auto;padding:0 1rem;line-height:1.5}</style>"
            f"<h1>{title}</h1><p>{detail}</p>"
        ),
    }


def lambda_handler(event, _context):
    instance_id = os.environ["INSTANCE_ID"]
    secret = os.environ["WAKE_SECRET"]
    boot_estimate = os.environ.get("BOOT_ESTIMATE", "3")

    params = (event.get("queryStringParameters") or {})
    supplied = params.get("key", "")

    # compare_digest rather than == : constant-time, so the response
    # timing does not leak how much of the secret was correct.
    if not hmac.compare_digest(supplied, secret):
        return _page("Not found", "Nothing here.", status=404)

    reservations = ec2.describe_instances(InstanceIds=[instance_id])
    state = (reservations["Reservations"][0]["Instances"][0]
             ["State"]["Name"])

    if state in LIVE_STATES:
        return _page(
            "Already awake",
            "The server is running (or starting). If you cannot connect "
            f"yet, give it up to {boot_estimate} minutes -- the modpack "
            "takes a while to load.",
        )

    if state != "stopped":
        # stopping / shutting-down / terminated: starting now would fail
        # or do something surprising. Say so plainly.
        return _page(
            "Not ready",
            f"The instance is currently <code>{state}</code>. Wait for it "
            "to finish and try again in a minute.",
        )

    ec2.start_instances(InstanceIds=[instance_id])
    return _page(
        "Waking the server",
        f"Starting up. Give it about {boot_estimate} minutes, then "
        "connect as usual. It will power itself off again once everyone "
        "has left.",
    )
