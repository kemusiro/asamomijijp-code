#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Make listening WAVs and an explicitly labelled legacy-Rev-C comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import scipy
from scipy import signal, optimize
from scipy.io import wavfile

RATE = 48000
LEGACY_RECORDING_SHA256 = '9b60afa73d6d53ce26a3d076fc13e13b197c5f2ef8e82715fb4209011fe8d61b'
DEFAULT_SSG_WEIGHT = 255 / 1024  # jt03: fm_snd + (psg_snd << 5)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pcm(path, samples):
    if not np.isfinite(samples).all() or np.max(abs(samples)) >= 1:
        raise ValueError('Nonfinite/clipped listening output')
    data = np.rint(samples * 32767).astype('<i2')
    wavfile.write(path, RATE, data)
    return {'sha256': digest(path), 'frames': len(data), 'sample_rate': RATE,
            'channels': 1 if data.ndim == 1 else data.shape[1],
            'peak_dbfs': float(20 * np.log10(max(1e-12, np.max(abs(samples))))),
            'full_scale_samples': int(np.count_nonzero(abs(data.astype(np.int32)) >= 32767))}


def mono(x):
    return np.column_stack([x, x])


def listening(directory, ssg_weight=DEFAULT_SSG_WEIGHT):
    rate, raw = wavfile.read(directory / 'stems-float.wav')
    if rate != RATE or raw.ndim != 2 or raw.shape[1] != 2 or not np.isfinite(raw).all():
        raise ValueError('Expected finite FM/SSG float stems at 48 kHz')
    # Remove positive PSG DAC DC; this is an explicit listening filter, not a board model.
    hp = signal.butter(1, 5, 'highpass', fs=RATE, output='sos')
    stems = signal.sosfilt(hp, raw, axis=0)
    mix = stems[:, 0] + ssg_weight * stems[:, 1]
    peak = max(float(abs(mix).max()), float(abs(stems[:, 0]).max()),
               float(abs(ssg_weight * stems[:, 1]).max()))
    gain = (10 ** (-3 / 20)) / max(peak, 1e-12)
    files = {}
    files['ysii-jt03-full.wav'] = pcm(directory / 'ysii-jt03-full.wav', mono(mix * gain))
    files['ysii-jt03-fm.wav'] = pcm(directory / 'ysii-jt03-fm.wav', stems[:, 0] * gain)
    files['ysii-jt03-ssg.wav'] = pcm(directory / 'ysii-jt03-ssg.wav', stems[:, 1] * ssg_weight * gain)
    files['ysii-jt03-25-35s.wav'] = pcm(directory / 'ysii-jt03-25-35s.wav', mono(mix[25*RATE:35*RATE] * gain))
    report = {'rate_hz': RATE, 'filter': 'one-pole causal 5 Hz highpass on each stem',
              'mix': 'FM/32768 + ssg_weight*(SSG_A+SSG_B+SSG_C)/255',
              'ssg_weight': ssg_weight, 'common_gain': gain,
              'headroom_db': 3, 'independent_stem_normalization': False,
              'notes': 'Digital mono duplicated to L/R. Does not model Rev C analog mixer/pot/ADC.',
              'numpy': np.__version__, 'scipy': scipy.__version__, 'files': files}
    (directory / 'audio.json').write_text(json.dumps(report, indent=2) + '\n')
    return stems, report


def power_envelope(x):
    filtered = signal.sosfilt(signal.butter(3, [80, 8000], 'bandpass', fs=RATE, output='sos'), x)
    return signal.fftconvolve(filtered * filtered, np.ones(960) / 960, mode='same')[::48]


def legacy_comparison(directory, stems, recording):
    if digest(recording) != LEGACY_RECORDING_SHA256:
        raise ValueError('This fixed alignment is only for the archived alpha.4 recording (SHA mismatch)')
    decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(recording),
                                      '-f', 'f32le', '-ar', str(RATE), '-ac', '1', 'pipe:1'])
    actual = np.frombuffer(decoded, '<f4').astype(float)
    # Previous alpha.4 analysis established these envelope offsets. Keep them fixed here;
    # do not optimize delays to conceal a JT03 mismatch.
    offset, fm_lag = 5.770, 0.046
    lag = round(fm_lag * RATE)
    fm = np.concatenate([np.zeros(lag), stems[:-lag, 0]])
    psg = stems[:, 1]
    end = min(35 * RATE, len(fm), len(actual) - round(offset * RATE))
    if end <= 30 * RATE:
        raise ValueError('Legacy reference must contain at least 35 source seconds')
    # Fit on song 1..24 s, keep song 25..35 s held out for listening/comparison.
    # Power fit only adjusts two constant gains; no pitch, EQ, envelope or event edits.
    ef, ep, ea = power_envelope(fm[:end]), power_envelope(psg[:end]), power_envelope(actual)
    t = np.arange(1000, 24000, 4)
    target = np.interp(t + offset * 1000, np.arange(len(ea)), ea)
    mat = np.column_stack([ef[t], ep[t], np.ones(len(t))])
    coef, _ = optimize.nnls(mat, target)
    if min(coef[:2]) <= 0:
        raise ValueError('FM/SSG calibration was degenerate; retain uncalibrated audio')
    fm_gain, ssg_gain = np.sqrt(coef[:2])
    fitted = fm_gain * fm + ssg_gain * psg
    start, stop = 25 * RATE, 35 * RATE
    a = actual[round(offset * RATE)+start:round(offset * RATE)+stop]
    b = fitted[start:stop]
    # One global level match after FM/SSG calibration, common output attenuation for A/B.
    match = np.sqrt(np.mean(a*a) / max(1e-15, np.mean(b*b)))
    b *= match
    gain = 10 ** (-3/20) / max(abs(a).max(), abs(b).max())
    sequence = np.concatenate([a*gain, np.zeros(RATE), b*gain])
    files = {
        'compare-A-revc-alpha4-25-35s.wav': pcm(directory / 'compare-A-revc-alpha4-25-35s.wav', mono(a*gain)),
        'compare-B-jt03-legacy-matched-25-35s.wav': pcm(directory / 'compare-B-jt03-legacy-matched-25-35s.wav', mono(b*gain)),
        'compare-AB-revc-then-jt03.wav': pcm(directory / 'compare-AB-revc-then-jt03.wav', mono(sequence))}
    ta = np.arange(25000, 35000, 4)
    target_test = np.interp(ta + offset*1000, np.arange(len(ea)), ea)
    predicted = coef[0]*ef[ta] + coef[1]*ep[ta] + coef[2]
    report = {'recording_sha256': digest(recording), 'recording_firmware': 'C 0.3.0-alpha.4 (historical)',
              'recording_offset_seconds': offset, 'extra_fm_delay_seconds': fm_lag,
              'offset_source': 'firmware-c/verification/alpha4-line-latency-analysis.json',
              'fit_train_song_seconds': [1, 24], 'held_out_song_seconds': [25, 35],
              'fit_method': 'NNLS 20 ms band-limited power envelopes; constant FM/SSG gains + noise floor',
              'fm_gain': float(fm_gain), 'ssg_gain': float(ssg_gain),
              'fitted_ssg_weight_relative_to_fm': float(ssg_gain/fm_gain),
              'global_B_rms_match': float(match), 'common_AB_gain': float(gain),
              'held_out_power_correlation': float(np.corrcoef(target_test, predicted)[0, 1]),
              'AB_order': 'A: historical real Rev C 10 s; silence 1 s; B: calibrated JT03 10 s',
              'limits': ['Gains and FM delay in B are calibrated to OLD alpha.4, not current accepted firmware.',
                         'Power-envelope correlation is not sample/phase identity or an audio compatibility pass.',
                         'Uncalibrated full mix and separated stems are retained independently.',
                         'No event edits, pitch shifts, dynamic compression or envelope smoothing.'],
              'files': files}
    (directory / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--ssg-weight', type=float, default=DEFAULT_SSG_WEIGHT)
    p.add_argument('--legacy-recording', type=Path)
    a = p.parse_args()
    if not 0 < a.ssg_weight <= 10:
        p.error('--ssg-weight must be positive and <= 10')
    stems, report = listening(a.directory, a.ssg_weight)
    if a.legacy_recording:
        legacy_comparison(a.directory, stems, a.legacy_recording)
    print('PASS: listening WAVs written; see audio.json and comparison.json')
