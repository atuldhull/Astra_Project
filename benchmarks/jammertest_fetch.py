"""Stream an FGI Jammertest 2023 raw I/Q recording, shrink it 8x on the fly, never store the original.

Source: FGI Jammer Test 2023 Repository (CC BY 4.0, Liaquat, Bhuiyan, Islam; FGI / National Land Survey of Finland),
https://etsin.fairdata.fi/dataset/2eee8cfd-db00-4e46-bd62-d7632c09c700 . LabSat 3 wideband, L1/E1 centre 1575.42 MHz,
30.69 MS/s complex int8 (I, Q interleaved).

Output (for GNSS-SDR, GPS L1 C/A): int8 interleaved I/Q at 30.69/8 = 3.83625 MS/s (low-pass FIR, +/-1.6 MHz),
plus per-100 ms spectrum statistics of the full-band input (a receiver-independent interference indicator).

usage: python benchmarks/jammertest_fetch.py NAME OUTDIR      (NAME e.g. JT23_4.1.5)
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
from scipy import signal

CR = "2eee8cfd-db00-4e46-bd62-d7632c09c700"
FS, DEC = 30.69e6, 8
BLOCK = int(FS / 10)  # 100 ms of complex samples


def url_for(name):
    body = json.dumps({"cr_id": CR, "file": f"/JammerTest2023/{name}/{name}_L1_E1.iq"}).encode()
    req = urllib.request.Request("https://etsin.fairdata.fi/api/v3/download/authorize", body,
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))["url"]


def main(name, outdir):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    taps = signal.firwin(97, 1.6e6, fs=FS)
    zi = np.zeros(len(taps) - 1, complex)
    curl = subprocess.Popen(["curl", "-sfL", "--retry", "5", url_for(name)], stdout=subprocess.PIPE, bufsize=1 << 24)
    stats, phase, scale = [], 0, None
    with (out / f"{name}_3836k_ibyte.part").open("wb") as fo:
        while True:
            b = curl.stdout.read(2 * BLOCK)
            if not b:
                break
            x = np.frombuffer(b[: len(b) // 2 * 2], np.int8).astype(np.float32)
            z = x[0::2] + 1j * x[1::2]
            # stats on the full 30.69 MHz band: power, share of power within +/-1 MHz, spectral flatness
            S = np.abs(np.fft.fft(z[: 1 << 16].reshape(16, -1), axis=1)) ** 2
            S = np.fft.fftshift(S.mean(0)); f = np.fft.fftshift(np.fft.fftfreq(S.size, 1 / FS))
            stats.append((float(np.mean(np.abs(z) ** 2)), float(S[np.abs(f) < 1e6].sum() / S.sum()),
                          float(np.exp(np.mean(np.log(S + 1e-12))) / np.mean(S))))
            y, zi = signal.lfilter(taps, 1.0, z, zi=zi)
            y = y[phase::DEC]; phase = (phase - len(z)) % DEC
            if scale is None:
                scale = 25.0 / max(np.std(y), 1e-9)  # fixed for the whole file: keeps power changes visible
            q = np.clip(np.round(y * scale), -127, 127)
            iq = np.empty(2 * len(q), np.int8); iq[0::2] = q.real; iq[1::2] = q.imag
            fo.write(iq.tobytes())
            if len(stats) % 600 == 0:
                print(f"{name}: {len(stats) / 10:.0f} s", flush=True)
    rc = curl.wait()
    np.savez(out / f"{name}_spectrum_stats.npz", t=np.arange(len(stats)) / 10.0, stats=np.array(stats),
             cols=np.array(["power", "inband_1MHz_share", "flatness"]))
    p = out / f"{name}_3836k_ibyte.part"
    p.rename(p.with_suffix(".iq"))
    print(f"{name}: done, {len(stats) / 10:.0f} s, curl rc={rc}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
