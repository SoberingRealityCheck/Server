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
 * Region layer (bake_regions.py): one byte per cell naming the region that picks biome variants.
 * 0 = no region. Layout: "EREG", u16 format, u16 cell, i32 i0, i32 j0, i32 width, i32 height, u8[width*height].
 */
public final class Regions {
    public final List<String> names;
    private final int cell, i0, j0, w, h;
    private final byte[] grid;

    Regions(Path file, List<String> names) throws IOException {
        this.names = List.copyOf(names);
        try (InputStream in = new GZIPInputStream(Files.newInputStream(file), 1 << 16)) {
            DataInputStream d = new DataInputStream(in);
            ByteBuffer hd = ByteBuffer.wrap(d.readNBytes(24)).order(ByteOrder.LITTLE_ENDIAN);
            if (hd.getInt(0) != 0x47455245 /* "EREG" */ || hd.getShort(4) != 1) throw new IOException("bad regions header");
            cell = hd.getShort(6); i0 = hd.getInt(8); j0 = hd.getInt(12); w = hd.getInt(16); h = hd.getInt(20);
            grid = d.readNBytes(w * h);
            if (grid.length != w * h) throw new IOException("regions file truncated");
        }
    }

    /** Region index at a block column (0 = none). */
    public int at(double x, double z) {
        int i = (int) Math.floor(x / cell) - i0, j = (int) Math.floor(z / cell) - j0;
        return i < 0 || j < 0 || i >= w || j >= h ? 0 : grid[j * w + i] & 0xff;
    }

    public String name(int r) { return r <= 0 || r > names.size() ? null : names.get(r - 1); }
}
