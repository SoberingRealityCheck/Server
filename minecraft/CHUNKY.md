# Pre-generating chunks with Chunky

Chunky is installed on the server and runs only when started. Run it when
nobody is playing: world generation is CPU- and disk-intensive.

By default, Chunky uses the world's spawn as the center. Choose a radius,
then start the job:

```bash
docker compose exec minecraft rcon-cli chunky world minecraft:overworld
docker compose exec minecraft rcon-cli chunky shape circle
docker compose exec minecraft rcon-cli chunky radius 3000
docker compose exec minecraft rcon-cli chunky start
```

To use a different center, set its X and Z coordinates in blocks before
starting, for example:

```bash
docker compose exec minecraft rcon-cli chunky center 500 1200
```

The radius is in **blocks**, not chunks: a 3,000-block radius is about
188 chunks from the center in each direction. To convert a chunk radius
to blocks, multiply by 16. A circle avoids generating the corners
outside that radius; use `chunky shape square` for a square footprint.

Check the job with:

```bash
docker compose exec minecraft rcon-cli chunky progress
```

Use `chunky pause` and `chunky continue` to suspend and resume it. Its
progress survives server restarts. `chunky cancel` discards the task.
Pre-generation can take hours and consume substantial disk space; check
available storage before choosing a large radius:

```bash
docker compose exec minecraft du -sh /data/world
df -h /
```

To target another dimension, change `chunky world` before starting, for
example to `minecraft:the_nether` or `minecraft:the_end`.
