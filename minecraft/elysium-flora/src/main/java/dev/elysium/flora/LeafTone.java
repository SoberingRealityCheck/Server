package dev.elysium.flora;

import net.minecraft.util.StringRepresentable;
import net.minecraft.world.level.block.state.properties.IntegerProperty;

/**
 * A leaf block's tone: one block, up to four shades of its own tint. Every LeavesBlock gets the `tone` property
 * (mixin.LeavesBlockMixin); 0 is the block as it always was. The client shifts the tint colour, whatever it is
 * (vanilla, the atlas's region palettes, Serene Seasons), by the tone (client.ToneColors). Untinted leaves
 * (cherry, azalea, fixed-colour mod leaves) carry the property but show no change.
 */
public enum LeafTone implements StringRepresentable {
    NONE("none"),
    /** Lighter and warmer: sun-facing tops, outer tips. */
    SUN("sun"),
    /** Darker: the crown's interior and its north side. */
    SHADE("shade"),
    /** Light and grey: undersides (white poplar, olive, whitebeam), frost, dust. */
    PALE("pale");

    public static final IntegerProperty TONE = IntegerProperty.create("tone", 0, 3);
    public static final StringRepresentable.EnumCodec<LeafTone> CODEC = StringRepresentable.fromEnum(LeafTone::values);

    private final String name;

    LeafTone(String name) {
        this.name = name;
    }

    @Override
    public String getSerializedName() {
        return this.name;
    }
}
