# Version 0.65 checkpoint

Version 0.65 adds the opening Cold War history card as a native game texture,
not a timed `demo.dat` subtitle. The resource is
`stage/v000a_0/cache.hpk`, HPK key `309d745f`, DARC member
`timg/cold_war_text_eng_alp_ovl.bclim` (400x64 L4, padded in its original
fixed-size member). Citra custom-texture testing confirmed the identified card;
hardware validation of the native BCLIM rebuild is pending.

The checkpoint also changes the first briefing's repeated Jack line from
`버추어스 미션?` to `버추(가상)미션?`, preserving both 20-byte subtitle
slots and the complete `movie.dat` record layout. Existing media normalization
already changes `버츄어스 미션` to `버추어스 미션`.

GCX 13 was found to contain accidental translations of internal encyclopedia
index strings. Its offset and size match the pristine Western record exactly
(offset `0x1C50`, 24,864 bytes), so v0.65 restores that entire non-dialogue GCX
from the pristine codec while preserving all 2,326 record boundaries.

Reproduction tools:

- `tools/mgs3d_history_texture.py`
- `tools/mgs3d_v065_media_fix.py`
- `tools/mgs3d_restore_gcx.py`
- `tools/mgs3d_hpk_inventory.py`

Local RomForge staging hashes after preparation:

- `codec.dat`: `86cc8e12504e517fd0916de95e3f7a46b7f00b9c6859c28338d187334493c524`
- `movie.dat`: `0f7e4c961ca4d10c19a46a7076ca0155a0531ed8b10f1a54b62d382a957945dd`
- `stage/v000a_0/cache.hpk`: `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`

No proprietary game data or generated CCI is committed.
