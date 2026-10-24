package dev.elysium.atlas;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.zip.GZIPInputStream;

/**
 * Region layer (bake_regions.py): one unit per cell (an ecoregion, or a piece of one) that picks biome variants.
 * 0 = no unit. Layout: "EREG", u16 format, u16 cell, i32 i0, i32 j0, i32 width, i32 height, then u8 (format 1)
 * or little-endian u16 (format 2) per cell. Held as 64x64-cell blocks; a block with one value stores no array.
 */
public final class Regions {
    public final List<String> names;
    private static final int B = 64;
    private final int cell, i0, j0, w, h, bw;
    private final short[][] blocks;
    private final short[] uniform;

    Regions(Path file, List<String> names) throws IOException {
        this.names = List.copyOf(names);
        try (InputStream in = new GZIPInputStream(Files.newInputStream(file), 1 << 16)) {
            DataInputStream d = new DataInputStream(in);
            ByteBuffer hd = ByteBuffer.wrap(d.readNBytes(24)).order(ByteOrder.LITTLE_ENDIAN);
            int format = hd.getShort(4);
            if (hd.getInt(0) != 0x47455245 /* "EREG" */ || format < 1 || format > 2) throw new IOException("bad regions header");
            cell = hd.getShort(6); i0 = hd.getInt(8); j0 = hd.getInt(12); w = hd.getInt(16); h = hd.getInt(20);
            int bpc = format; bw = (w + B - 1) / B; int bh = (h + B - 1) / B;
            blocks = new short[bw * bh][]; uniform = new short[bw * bh];
            short[][] rows = new short[B][w];
            byte[] row = new byte[w * bpc];
            for (int by = 0; by < bh; by++) {
                int nr = Math.min(B, h - by * B);
                for (int r = 0; r < nr; r++) {
                    d.readFully(row);
                    for (int c = 0; c < w; c++)
                        rows[r][c] = bpc == 1 ? (short) (row[c] & 0xff) : (short) ((row[2 * c] & 0xff) | (row[2 * c + 1] & 0xff) << 8);
                }
                for (int bx = 0; bx < bw; bx++) {
                    int nc = Math.min(B, w - bx * B); short first = rows[0][bx * B]; boolean same = true;
                    short[] blk = new short[B * B];
                    for (int r = 0; r < nr; r++)
                        for (int c = 0; c < nc; c++) { short v = rows[r][bx * B + c]; blk[r * B + c] = v; same &= v == first; }
                    if (same) uniform[by * bw + bx] = first; else blocks[by * bw + bx] = blk;
                }
            }
        }
    }

    /** Region index at a block column (0 = none). */
    public int at(double x, double z) {
        int i = (int) Math.floor(x / cell) - i0, j = (int) Math.floor(z / cell) - j0;
        if (i < 0 || j < 0 || i >= w || j >= h) return 0;
        int k = (j / B) * bw + i / B; short[] blk = blocks[k];
        return (blk == null ? uniform[k] : blk[(j % B) * B + i % B]) & 0xffff;
    }

    public String name(int r) { return r <= 0 || r > names.size() ? null : names.get(r - 1); }
}
