# MT7932 enterprise Wi-Fi investigation

Status: **not implemented; not an eduroam fix**. This branch adds a diagnostic
for rejected security requests and prepares a reproducible external-module build.
It does not enable enterprise authentication or change security admission.

## Confirmed source-level blockers

At upstream revision `b798f2b0c767e3d780896cff2f57e19e412bf954`:

- `association.h:mt7932_connect_auth()` accepts PSK, SAE and OWE, not the
  `WLAN_AKM_SUITE_8021X` used by WPA2-Enterprise.
- `association.h:mt7932_connect_body()` describes firmware-owned OPEN, OWE,
  PSK and SAE requests. An enterprise firmware request layout is not established.
- `startup.c:mt_cfg_ops` has no host key installation or PMK update callbacks.
- `packet.h:mt7932_rx_protection_ok()` rejects unprotected frames on secure links.
  EAPOL requires a deliberately scoped control-port exception, not bypassing
  protection checks for ordinary traffic.
- `link.c` reports port authorization after the firmware-owned handshake.
  Enterprise must not authorize ordinary data merely because association succeeds.

The driver's rejection explains why a userspace "secrets required" error is not
evidence of an incorrect university password. Passwords, account identifiers,
Wi-Fi profiles and firmware/calibration contents must not be committed here.

## Work required before claiming enterprise support

1. Establish the actual firmware interface for enterprise association and
   EAPOL transport. Do not guess command offsets or reuse OPEN/PSK as a fallback.
2. Select a supported handshake ownership model:
   - host EAP and host four-way handshake with validated key install/delete; or
   - host EAP followed by a documented firmware PMK handoff and handshake.
3. Implement controlled-port gating, EAPOL TX/RX, key lifetimes, rekeying,
   disconnect cleanup and stale event exclusion for that model.
4. Advertise only capabilities that are actually implemented.
5. Exercise a controlled AP/RADIUS test environment before a production eduroam
   login, including wrong credentials, wrong server certificate, disconnects,
   reconnects and group rekey. Never disable server certificate validation.
6. Confirm DHCP and real connectivity, and regress OPEN, PSK, SAE and OWE.

Removing the AKM rejection alone is not a solution. It would pass an unsupported
request into a firmware builder that currently has no enterprise representation.

## Baseline module build (no installation)

From the repository root:

```sh
bash tools/asahi/build-mt7932-module.sh
```

The script builds against the running kernel's installed headers, with two jobs
by default. `KERNEL_RELEASE`, `JOBS` and `CLANG` can override those choices.
The compiler major version must match the kernel build compiler. The resulting
module is a development artifact only: **do not unload working Wi-Fi, copy it
over a packaged module, run depmod, or reboot into it without a recovery plan**.

This source checkout may be newer than the installed kernel package even when
the external-module build succeeds. Compilation does not establish ABI safety,
firmware compatibility or working enterprise authentication.

## Validation on the development machine

- Built `mt7932-fullmac.ko` using Clang 18.1.8 and the installed
  `7.2.11-14-1-ARCH` headers. Vermagic matches that kernel release.
- `python3 tools/asahi/mt7932-enterprise-admission-tests.py`: passed; confirms
  existing enterprise rejection, PSK baseline and no fallback/downgrade.
- `python3 tools/asahi/mt7932-association-events-tests.py --out <directory>`:
  all 28 production controls passed; all four negative mutation controls failed
  as expected.
- Module was **not loaded or installed**. No hardware acceptance or enterprise
  connectivity success is claimed.
