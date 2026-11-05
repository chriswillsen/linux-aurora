#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the actual admission helper; rejection is not enterprise support."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "drivers/net/wireless/mediatek/mt7932/association.h"

PREFIX = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define NL80211_WPA_VERSION_2 2
#define NL80211_WPA_VERSION_3 4
#define NL80211_MFP_NO 0
#define NL80211_MFP_REQUIRED 1
#define NL80211_MFP_OPTIONAL 2
#define NL80211_AUTHTYPE_OPEN_SYSTEM 0
#define NL80211_AUTHTYPE_SAE 4
#define NL80211_SAE_PWE_UNSPECIFIED 0
#define NL80211_SAE_PWE_HUNT_AND_PECK 1
#define NL80211_SAE_PWE_HASH_TO_ELEMENT 2
#define NL80211_SAE_PWE_BOTH 3
#define WLAN_CIPHER_SUITE_CCMP 0x000fac04
#define WLAN_AKM_SUITE_8021X 0x000fac01
#define WLAN_AKM_SUITE_PSK 0x000fac02
#define WLAN_AKM_SUITE_8021X_SHA256 0x000fac05
#define WLAN_AKM_SUITE_SAE 0x000fac08
#define WLAN_AKM_SUITE_OWE 0x000fac12
#define MT7932_SAE_PASSWORD_MIN 8
#define MT7932_SAE_PASSWORD_MAX 63
struct cfg80211_connect_params {
    int auth_type, mfp;
    const void *key;
    unsigned key_len;
    bool want_1x;
    struct {
        u32 wpa_versions, ciphers_pairwise[2], cipher_group, akm_suites[2];
        int n_ciphers_pairwise, n_akm_suites;
        const void *psk, *sae_pwd;
        unsigned sae_pwd_len, sae_pwe;
    } crypto;
};
"""

TEST = r"""
int main(void)
{
    const u32 enterprise[] = {WLAN_AKM_SUITE_8021X, WLAN_AKM_SUITE_8021X_SHA256};
    unsigned char pmk[32] = {0};
    struct cfg80211_connect_params p = {
        .auth_type = NL80211_AUTHTYPE_OPEN_SYSTEM,
        .mfp = NL80211_MFP_NO,
        .crypto = {
            .wpa_versions = NL80211_WPA_VERSION_2,
            .n_ciphers_pairwise = 1,
            .ciphers_pairwise = {WLAN_CIPHER_SUITE_CCMP},
            .cipher_group = WLAN_CIPHER_SUITE_CCMP,
            .n_akm_suites = 1,
            .akm_suites = {WLAN_AKM_SUITE_PSK},
            .psk = pmk,
        },
    };

    assert(mt7932_connect_auth(&p) == WLAN_AKM_SUITE_PSK);
    for (unsigned i = 0; i < sizeof(enterprise) / sizeof(*enterprise); i++) {
        p.crypto.akm_suites[0] = enterprise[i];
        p.crypto.psk = NULL;
        assert(mt7932_connect_auth(&p) == -EOPNOTSUPP);
        /* Supplying a PMK must not turn enterprise into PSK. */
        p.crypto.psk = pmk;
        assert(mt7932_connect_auth(&p) == -EOPNOTSUPP);
        /* A supported secondary AKM must not silently downgrade security. */
        p.crypto.n_akm_suites = 2;
        p.crypto.akm_suites[1] = WLAN_AKM_SUITE_PSK;
        assert(mt7932_connect_auth(&p) == -EOPNOTSUPP);
        p.crypto.n_akm_suites = 1;
    }
    p.crypto.akm_suites[0] = WLAN_AKM_SUITE_PSK;
    p.crypto.n_akm_suites = 0;
    assert(mt7932_connect_auth(&p) == -EOPNOTSUPP);
    puts("PASS: PSK baseline, enterprise rejection, no PMK bypass or AKM downgrade");
}
"""


def main():
    source = SOURCE.read_text()
    start = source.index("static inline int\nmt7932_connect_auth(")
    opening = source.index("{", start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    with tempfile.TemporaryDirectory(prefix="mt7932-admission-") as directory:
        path = Path(directory)
        fixture = path / "admission.c"
        binary = path / "admission"
        fixture.write_text(PREFIX + source[start:end] + TEST)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        str(fixture), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
