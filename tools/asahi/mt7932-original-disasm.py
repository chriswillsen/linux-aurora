#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Produce local analysis artifacts from an owner's original macOS driver.

Never add the input binary, thin slice, or disassembly to this repository.
This tool reads the supplied file only; it neither mounts nor executes it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SYMBOLS = {
    "station-key-wrapper": "__ZN30AppleSunriseWLANInfraInterface13setCIPHER_KEYEP14apple80211_key",
    "station-key-update": "_gl_io80211_set_pmk",
    "station-key-delete": "_gl_io80211_del_pmk",
    "enterprise-classification": "__Z23is_upperAuth_enterpriseP25apple80211AssocCandidates",
    "station-connect": "_gl_io80211_connect",
    "firmware-connect": "_assocSendConnectCmd",
    "extended-command-transport": "_wlanSendSetQueryExtCmd",
    "security-frame-descriptor": "_nic_txd_v2_compose_security_frame",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--out", type=Path, required=True,
                        help="private output directory outside the kernel repository")
    parser.add_argument("--llvm-bin", type=Path, default=Path("/usr/lib/llvm18/bin"))
    args = parser.parse_args()
    source, out = args.binary.resolve(), args.out.resolve()
    if out.is_relative_to(ROOT):
        parser.error("keep proprietary analysis artifacts outside the repository")
    if source.is_relative_to(out):
        parser.error("use an output directory separate from the original binary")
    if out.exists():
        parser.error("use a new output directory to avoid overwriting earlier analysis")

    os.umask(0o077)
    out.mkdir(parents=True, mode=0o700)
    llvm = args.llvm_bin
    listing = subprocess.run(
        [str(llvm / "llvm-nm"), "--arch=arm64e", "--numeric-sort", "--defined-only", str(source)],
        check=True, capture_output=True, text=True).stdout
    functions = []
    for line in listing.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]+) [tT] (\S+)", line)
        if match:
            functions.append((int(match[1], 16), match[2]))
    functions.sort()
    addresses = {name: address for address, name in functions}
    missing = sorted(set(SYMBOLS.values()) - addresses.keys())
    if missing:
        parser.error("required symbols missing in this driver version: " + ", ".join(missing))

    thin = out / "original.arm64e"
    subprocess.run([str(llvm / "llvm-lipo"), str(source), "-thin", "arm64e",
                    "-output", str(thin)], check=True)
    report = {"original_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "original_bytes": source.stat().st_size, "architecture": "arm64e", "symbols": {}}
    for label, symbol in SYMBOLS.items():
        address = addresses[symbol]
        end = next((value for value, _ in functions if value > address), None)
        if end is None:
            parser.error("cannot determine end of " + symbol)
        result = subprocess.run(
            [str(llvm / "llvm-objdump"), "-d", f"--start-address={address:#x}",
             f"--stop-address={end:#x}", str(thin)],
            check=True, capture_output=True, text=True)
        (out / (label + ".asm")).write_text(result.stdout)
        report["symbols"][label] = {"symbol": symbol, "start": hex(address), "end": hex(end)}
    (out / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Extracted {len(SYMBOLS)} routine ranges into {out}.")
    print("These are private analysis artifacts, not an enterprise-support implementation.")


if __name__ == "__main__":
    main()
