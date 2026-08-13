# Unpacked MGS3D integrity baseline

The working `partition0` directory is treated as read-only source material.
Translation builds and experiments must be written under `analysis` or `dist`.
The tools do not patch `partition0/romfs/codec.dat` in place.

## Audit result

All files under `partition0` retain timestamps from the single extraction window
on 2026-07-31 around 18:06:35–18:06:41. No file has a later timestamp from the
tool-development or Korean smoke-test work.

The current `codec.dat` SHA-256 is:

```text
932c0a13dd4a0a55213e0a2352b12a11b496a7216706838d0d044930789a344f
```

It is also the hash recorded before the rebuild tests, and a no-change rebuild
was byte-identical to it. The file parses as 2,326 sequential GCX records with
198,227 resources.

The baseline contains 925 files totaling 3,097,453,107 bytes. Additional key
hashes are:

```text
demo.dat     3c451c665ea415ce7b260505eee7f1674bf2169949be90caa45f4b58f09dbe39
code.bin     d81a3ad51869fd8e0f716925fc1a3303366f7427b8e99953d1a5b504bcdc97f1
exheader.bin 464f54680fd72bae4d53ef4b611aa7cbd2be2372e02ca8ebc4e87f3fae06fbae
```

All 232 DARC archives detected by magic parsed successfully, comprising 2,240
archive entries. This is a structural check in addition to the hash inventory.

The original MGS3D CIA/3DS container is not present in this workspace. Therefore
this manifest proves that files remain equal to the audited working baseline;
it cannot independently prove equality to a missing retail container. If the
original image is supplied later, it should be unpacked into a separate folder
and compared before replacing this baseline.

## Verify before work

```powershell
python tools/audit_unpacked.py verify `
  partition0 docs/unpacked-baseline.json
```

Any added, missing, resized, or byte-changed file makes the command fail. Do not
refresh the baseline merely to clear a failure; first identify why it changed.
