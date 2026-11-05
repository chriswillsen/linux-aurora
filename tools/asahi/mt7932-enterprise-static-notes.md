# Original-driver static investigation

**Status: initial observations, not a working enterprise implementation.**

## Input and acquisition

The owner authorized read-only access to the macOS installation on the J700.
Only the unencrypted System snapshot was mounted. The reader opened the device
with `O_RDONLY`, the loop mapping was kernel-enforced read-only, and the FUSE
mount was `ro,nodev,nosuid,noexec`. The encrypted Data volume was not opened;
no macOS password was needed. The mount and loop mapping were removed after
copying the driver and bundle metadata into a private directory outside Git.

The local APFS reader needed a modern-compiler header fix. Its container parser
also stopped at an unsupported keybag before listing unencrypted volumes. The
local build was adjusted to allow metadata/unencrypted volumes while explicitly
refusing encrypted volumes and snapshots. No checksum checks were disabled, and
no APFS metadata was modified. Do not confuse this with support for decrypting
Apple Silicon Data volumes.

Original executable: `com.apple.AppleSunriseWLAN`, from macOS 27.2 build 26B123.

- Universal executable size: 11,459,248 bytes.
- SHA-256: `ceaebd0c40caa0666ef9bcc6f31003dc67ef5762bedad42d0ce04f279ab67297`.
- Analysis slice: arm64e. All addresses below are unslid addresses in this slice.
- Original binaries and disassembly remain private; they are not redistributed
  in this repository. The version may differ from the source used to establish
  the existing Linux firmware builders. Cross-version compatibility is unproven.

## Observed station key-update path

`AppleSunriseWLANInfraInterface::setCIPHER_KEY(apple80211_key *)` at
`0x100049fcc` passes its key argument directly to `gl_io80211_set_pmk` at
`0x10029b0c0`. This is the infrastructure/station wrapper, not a NAN or AP
key-install routine. Despite its name, do not assume the latter routine only
handles a bare PMK: its caller supplies an Apple cipher-key structure.

In its nonzero-key-length branch, `gl_io80211_set_pmk` constructs a zero-initialized
stack payload and calls `wlanSendSetQueryExtCmd` at `0x10010feb0` with:

- Command ID `0xea`, extended ID `0x41`.
- Payload size `0x15c` (348 bytes).
- Set flag 1; response-needed flag 0; OID flag 0.
- Null done/timeout callback arguments at this call site.

The command call is at `0x10029b2a8`. The transport stores the IDs into its
header argument structure, confirming these are command identifiers rather
than inferred names. A successful submission is **not** evidence of completed
key installation or successful authentication.

Selected byte-copy observations (not a complete firmware schema):

| Payload offset | Source in input key object | Bytes |
| --- | --- | --- |
| `0x00` | `0x00` | `0x50` |
| `0xd8` | `0x50` | 4 |
| `0xdc` | `0x54` | 8 |
| `0xe4` | `0x5c`, or current BSS address at BSS-info `+0x44` | 6 |
| `0xec` | `0x64` | 4 |
| `0xf0` | `0x68` | 16 |
| `0x110` | `0x78` | 4 |
| `0x114` | `0x7c` | 16 |
| `0x154` | `0x8c` | 8 |

The first input word after the version-like word is checked for zero before
this branch. Field meanings, accepted key types, index/flag encoding, deletion,
key replay counters and the installation completion event are not established.
The zero-length branch and `gl_io80211_del_pmk` require separate analysis.

## Association and enterprise entry points

- `is_upperAuth_enterprise(apple80211AssocCandidates *)` at `0x1002987dc`
  classifies the 32-bit field at input `+0x14`. Its accepted values include
  `1`, `4`, `32`, `0x80`, `0x800`, `0x4000` and `0x8000`. These are Apple's
  classification values, **not nl80211 AKM identifiers**.
- `gl_io80211_connect` at `0x100298840` consults this classification and has a
  path calling `gl_io80211_del_pmk`. Do not copy PSK behavior into enterprise
  based only on a similar-looking association request.
- `wlanoidSendConnectCmd` at `0x10010fce8` passes to `assocSendConnectCmd` at
  `0x1003606d0`.
- At `0x100361ec8`, this version of `assocSendConnectCmd` selects a payload
  length of `0x364` (868 bytes), then submits `0xea/0x40` at `0x100361f0c`.
  The Linux builder currently submits **856 bytes** to that same command.
  Therefore the original-driver version is not a drop-in struct specification
  for the current Linux implementation. Determine layout/firmware compatibility
  rather than appending padding or sending the newer structure blindly.
- `nic_txd_v2_compose_security_frame` exists. EAPOL descriptor flags and receive
  routing must be established before using the ordinary Ethernet DMA path for
  host authentication frames.

## Reproduce locally

Install LLVM tools and run, using a new private output directory outside Git:

```sh
python3 tools/asahi/mt7932-original-disasm.py /private/path/to/AppleSunriseWLAN \
  --out /private/path/to/new-analysis-directory
```

The helper records provenance and disassembles eight named routines from the
owner's binary. It does not run the macOS executable, access a disk device,
mount a filesystem, or retrieve any password.

## Still required

Establish the firmware enterprise association tuple, precise key-update/delete
schema, EAPOL TX/RX path and controlled-port ownership. Then implement and test
the Linux callbacks and state transitions against an isolated AP/RADIUS setup,
followed by a real certificate-validated eduroam connection. None of those
completion claims follows from finding a symbol or decoding a command number.
