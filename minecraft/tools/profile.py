#!/usr/bin/env python3
"""Profile lag on the Elysium server or on your own game client.

    python3 minecraft/tools/profile.py server [--seconds 120]
    python3 minecraft/tools/profile.py client [--seconds 120]

Run `server` from the repo root on the game host. It drives the
container through `docker compose exec minecraft rcon-cli`, same as the
other *_live.py tools. Run `client` on the machine that runs the game.

It only means something while players are online and the lag is
happening. An idle server profiles as nothing. Join, go to the laggy
place (new terrain, a farm, the DH area), then start the script.

SERVER mode, in order:
  1. prints spark's own help for `profiler`, so a wrong flag shows up
  2. snapshot: tps, memory, gc
  3. starts spark with --thread * and --only-ticks-over 50, so it only
     records slow ticks and spikes don't get averaged away
  4. waits, then stops spark and grabs the report link
  5. counts "Can't keep up" lines in the container log for the window

CLIENT mode: spark on the client only takes /sparkc typed into chat, no
rcon. So this uses JFR (Java Flight Recorder) on the running game JVM:
  1. finds the game process, then jcmd JFR.start for N seconds
  2. reads the .jfr file: busiest threads + hottest top frames
  3. counts DH warnings and "Can't keep up" in the client latest.log
If jcmd is missing or can't attach (launchers often bundle a JRE with
no jcmd), it says so and prints the /sparkc lines to paste instead.

Heads up:
  - spark report links are PUBLIC (anyone with the link can open it).
  - Reports land in profiling/<timestamp>/report.txt (gitignored).
  - Nothing here was run against a live server/client when written.
    The JFR parser was only tested on a toy JFR file. The spark
    flags are from memory of 1.10.x. Step 1 shows if one is wrong.
"""
import argparse, collections, datetime, os, re, shutil, subprocess, sys, time

OUT = None  # report dir, set in main()
LINES = []  # everything we print, saved to report.txt


def say(msg=""):
    print(msg, flush=True)
    LINES.append(msg)


def run(cmd, timeout=120):
    """Run a command, return (exit code, stdout+stderr). Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def clean(s):
    # strip ansi + minecraft section-sign color codes
    s = re.sub(r"\x1b\[[0-9;]*m", "", s)
    return re.sub(r"§.", "", s)


# ---------------------------------------------------------------- server

def rcon(cmd):
    _, out = run(["docker", "compose", "exec", "-T", "minecraft", "rcon-cli", cmd])
    return clean(out)


def count_behind(log):
    """Parse 'Running 5123ms (102 ticks) behind' lines. Returns (n, ms, ticks)."""
    hits = re.findall(r"Can't keep up!.*?Running (\d+)ms.*?(\d+) ticks", log)
    return len(hits), sum(int(a) for a, _ in hits), sum(int(b) for _, b in hits)


def server(seconds):
    say("== 0. who is on")
    who = rcon("list")
    say(who)
    if re.search(r"There are 0 of", who):
        say("!! nobody online. The profile will be empty. Join first.")

    say("\n== 1. spark profiler help (check the flags we use exist)")
    say(rcon("spark profiler"))

    say("\n== 2. snapshot before")
    for c in ["spark tps", "spark health --memory", "spark gc"]:
        say(f"-- {c}")
        say(rcon(c))

    say("\n== 3. start profiler")
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = rcon("spark profiler start --thread * --only-ticks-over 50")
    say(out)
    if not re.search(r"started|running", out, re.I):
        say("!! start did not look right. Retrying without --only-ticks-over.")
        out = rcon("spark profiler start --thread *")
        say(out)
        if not re.search(r"started|running", out, re.I):
            say("!! still no. Read the help in step 1 and fix the flags. Stopping.")
            return

    say(f"\n== 4. recording for {seconds}s")
    time.sleep(seconds)
    out = rcon("spark profiler stop")
    say(out)
    urls = re.findall(r"https://spark\.lucko\.me/\S+", out)
    if not urls:
        # some versions only log the link. look in the container log.
        _, log = run(["docker", "compose", "logs", "--no-log-prefix", "--since", start, "minecraft"])
        urls = re.findall(r"https://spark\.lucko\.me/\S+", clean(log))
    say(f"report link: {urls[-1] if urls else 'NOT FOUND, check `docker compose logs minecraft`'}")

    say("\n== 5. snapshot after")
    for c in ["spark tps", "spark health --memory"]:
        say(f"-- {c}")
        say(rcon(c))

    say("\n== 6. 'Can't keep up' in the log for this window")
    _, log = run(["docker", "compose", "logs", "--no-log-prefix", "--since", start, "minecraft"])
    n, ms, ticks = count_behind(clean(log))
    say(f"{n} warnings, {ms} ms total, {ticks} ticks behind")

    say("\n== summary")
    say(f"window: {seconds}s | can't-keep-up: {n} ({ticks} ticks) | report: {urls[-1] if urls else 'none'}")
    say("Open the report. Look at the 'Server thread' tree, biggest self-time first.")
    say("Chunk gen / entity ticking / a single mod name at the top is your answer.")


# ---------------------------------------------------------------- client

SPARKC = [
    "/sparkc profiler start --thread * --only-ticks-over 50",
    "(wait, play, hit the lag)",
    "/sparkc profiler stop",
]


def find_game():
    """Return (pid, gameDir or None) of a running Fabric client, else (None, None)."""
    _, out = run(["pgrep", "-f", "net.fabricmc.loader.impl.launch.knot.KnotClient"])
    pids = [p for p in out.split() if p.isdigit() and int(p) != os.getpid()]
    if not pids:
        return None, None
    pid = pids[0]
    _, args = run(["ps", "-o", "args=", "-p", pid])
    m = re.search(r"--gameDir\s+(.+?)\s+--", args + " --")
    return pid, (m.group(1) if m else None)


def find_tool(name):
    """jcmd / jfr: PATH first, then JAVA_HOME, then the macOS java_home."""
    t = shutil.which(name)
    if t:
        return t
    homes = [os.environ.get("JAVA_HOME", "")]
    _, jh = run(["/usr/libexec/java_home"])
    homes.append(jh)
    for h in homes:
        p = os.path.join(h, "bin", name)
        if h and os.path.exists(p):
            return p
    return None


def parse_jfr(text):
    """Count execution samples by thread and by (thread, top frame).

    Input is `jfr print --events jdk.ExecutionSample --stack-depth 1`.
    Each event has `sampledThread = "Render thread" (...)` then
    `stackTrace = [` and the top frame on the next line.
    Hack: text scraping. If the format changes this returns empty.
    """
    threads = collections.Counter()
    frames = collections.Counter()
    thread = None
    want_frame = False
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r'sampledThread = "([^"]*)"', s)
        if m:
            thread = m.group(1)
            threads[thread] += 1
        elif s.startswith("stackTrace = ["):
            want_frame = True
        elif want_frame:
            frames[(thread, re.sub(r"\s+line:.*", "", s))] += 1
            want_frame = False
    return threads, frames


def jfr_gc(text):
    """Total GC pause from `jfr print --events jdk.GarbageCollection`."""
    ms = re.findall(r"sumOfPauses = ([\d.]+) (ms|s)", text)
    total = sum(float(v) * (1000 if u == "s" else 1) for v, u in ms)
    return len(ms), total


def client(seconds):
    say("== 1. find the game")
    pid, gamedir = find_game()
    if not pid:
        say("!! no Fabric client running. Start the game, join the server, then rerun.")
        return
    say(f"pid {pid}, gameDir {gamedir}")

    jcmd, jfr = find_tool("jcmd"), find_tool("jfr")
    log_start = None
    jfr_file = os.path.join(OUT, "client.jfr")
    ok = False
    if jcmd and jfr:
        say(f"\n== 2. JFR for {seconds}s (go hit the lag now)")
        code, out = run([jcmd, pid, "JFR.start", "name=elysium", "settings=profile",
                         f"duration={seconds}s", f"filename={jfr_file}"])
        say(out)
        if code == 0:
            time.sleep(seconds + 5)
            ok = os.path.exists(jfr_file)
            if not ok:
                # duration end writes the file. if not, dump it by hand.
                run([jcmd, pid, "JFR.dump", "name=elysium", f"filename={jfr_file}"])
                ok = os.path.exists(jfr_file)
        else:
            say("!! jcmd could not attach. Likely a java version mismatch with the game.")
    else:
        say(f"\n!! missing tool(s): {'jcmd ' if not jcmd else ''}{'jfr' if not jfr else ''}")
        say("Launchers often bundle a JRE with no jcmd. Install a JDK (same major as the")
        say("game's java, 25) and put it on PATH, or set JAVA_HOME.")

    if ok:
        say("\n== 3. read the recording")
        _, txt = run([jfr, "print", "--events", "jdk.ExecutionSample", "--stack-depth", "1", jfr_file], timeout=300)
        threads, frames = parse_jfr(txt)
        total = sum(threads.values()) or 1
        say(f"{total} cpu samples. Busiest threads:")
        for t, n in threads.most_common(6):
            say(f"  {n:6}  {100*n//total:3}%  {t}")
        for t in [t for t, _ in threads.most_common(2)]:
            say(f"hottest top frames on '{t}':")
            top = [(f, n) for (th, f), n in frames.most_common() if th == t][:10]
            for f, n in top:
                say(f"  {n:6}  {f}")
        _, gctxt = run([jfr, "print", "--events", "jdk.GarbageCollection", jfr_file], timeout=120)
        gcn, gcms = jfr_gc(gctxt)
        say(f"GC: {gcn} collections, {gcms:.0f} ms total pause")
    else:
        say("\n== fallback: use spark in game")
        say("Type these in chat:")
        for l in SPARKC:
            say("  " + l)
        say("The stop command prints a link to the report.")

    say("\n== 4. client log")
    log = os.path.join(gamedir, "logs", "latest.log") if gamedir else None
    if log and os.path.exists(log):
        with open(log, errors="replace") as f:
            text = f.read()
        n, ms, ticks = count_behind(text)
        dh = [l for l in text.splitlines() if "DistantHorizons" in l.replace(" ", "") and re.search(r"WARN|ERROR", l)]
        say(f"can't keep up: {n} ({ticks} ticks, {ms} ms) | DH warn/error lines: {len(dh)}")
        for l in dh[-8:]:
            say("  " + l[:200])
    else:
        say(f"no log found at {log}")

    say("\n== summary")
    say("Render thread on top -> client rendering (DH, shaders, entities). Server thread")
    say("on top -> the integrated server. Many 'Worker-*' / DH threads -> LOD generation.")


# ---------------------------------------------------------------- main

def main():
    global OUT
    ap = argparse.ArgumentParser(description="Profile Elysium lag (server or client).")
    ap.add_argument("mode", choices=["server", "client"])
    ap.add_argument("--seconds", type=int, default=120, help="how long to record (default 120)")
    a = ap.parse_args()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    OUT = os.path.join("profiling", f"{ts}-{a.mode}")
    os.makedirs(OUT, exist_ok=True)
    try:
        (server if a.mode == "server" else client)(a.seconds)
    finally:
        with open(os.path.join(OUT, "report.txt"), "w") as f:
            f.write("\n".join(LINES) + "\n")
        print(f"\nsaved {OUT}/report.txt")


if __name__ == "__main__":
    main()
