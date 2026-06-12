from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np


class FakeBackend:
    PULSEAUDIO = "pulse"
    ALSA = "alsa"
    JACK = "jack"
    COREAUDIO = "coreaudio"
    WASAPI = "wasapi"
    DSOUND = "dsound"
    WINMM = "winmm"


class FakeSampleFormat:
    FLOAT32 = "float32"


class FakeDecoded:
    def __init__(self, samples, sample_rate=44100, channels=2) -> None:
        self.samples = samples
        self.sample_rate = sample_rate
        self.nchannels = channels


class FakePlaybackDevice:
    instances: list["FakePlaybackDevice"] = []
    fail_start = False

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False
        self.instances.append(self)

    def start(self, stream) -> None:
        if self.fail_start:
            raise RuntimeError("no output device")
        self.started = True
        self.stream = stream

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


DECODED = FakeDecoded(np.zeros(2, dtype=np.float32))
DECODE_CALLS = 0


def fake_decode_file(path, *, output_format, nchannels):
    global DECODE_CALLS
    DECODE_CALLS += 1
    del path
    assert output_format == FakeSampleFormat.FLOAT32
    assert nchannels == 2
    return DECODED


miniaudio = types.ModuleType("miniaudio")
miniaudio.Backend = FakeBackend
miniaudio.SampleFormat = FakeSampleFormat
miniaudio.PlaybackDevice = FakePlaybackDevice
miniaudio.decode_file = fake_decode_file
sys.modules["miniaudio"] = miniaudio

from audio_engine import AudioEngine


class AudioEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        global DECODED, DECODE_CALLS
        DECODED = FakeDecoded(np.zeros(2, dtype=np.float32))
        DECODE_CALLS = 0
        FakePlaybackDevice.instances.clear()
        FakePlaybackDevice.fail_start = False
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        self.path = Path(handle.name)

    def tearDown(self) -> None:
        self.path.unlink(missing_ok=True)

    def test_stereo_stream_and_single_end_event(self) -> None:
        global DECODED
        samples = np.array(
            [[0.1, -0.1], [0.25, -0.25], [0.5, -0.5]],
            dtype=np.float32,
        )
        DECODED = FakeDecoded(samples.ravel(), sample_rate=10)
        engine = AudioEngine()

        self.assertTrue(engine.open(self.path))
        self.assertTrue(engine.play())
        device = FakePlaybackDevice.instances[-1]
        self.assertEqual(device.kwargs["nchannels"], 2)

        first = device.stream.send(2)
        np.testing.assert_allclose(first, samples[:2])
        final = device.stream.send(2)
        np.testing.assert_allclose(final[0], samples[2])
        np.testing.assert_allclose(final[1], np.zeros(2))

        self.assertFalse(engine.is_playing())
        self.assertTrue(engine.consume_end_event())
        self.assertFalse(engine.consume_end_event())

    def test_empty_decode_clears_previously_loaded_audio(self) -> None:
        global DECODED
        engine = AudioEngine()
        self.assertTrue(engine.open(self.path))
        engine.clear_cache()
        DECODED = FakeDecoded(np.array([], dtype=np.float32))

        self.assertFalse(engine.open(self.path))
        self.assertEqual(engine.duration_sec(), 0)
        self.assertIsNone(engine.current_path())

    def test_output_start_failure_is_reported(self) -> None:
        engine = AudioEngine()
        self.assertTrue(engine.open(self.path))
        FakePlaybackDevice.fail_start = True

        self.assertFalse(engine.play())
        self.assertFalse(engine.is_playing())
        self.assertIn("no output device", engine.last_error())

    def test_non_positive_visualizer_chunks_are_rejected(self) -> None:
        engine = AudioEngine()
        self.assertTrue(engine.open(self.path))
        self.assertIsNone(engine.get_pcm_chunk(0))
        self.assertIsNone(engine.get_pcm_chunk(-1))

    def test_preload_keeps_playback_unchanged_and_open_reuses_cache(self) -> None:
        global DECODE_CALLS
        engine = AudioEngine()

        self.assertTrue(engine.preload(self.path).ok)
        self.assertIsNone(engine.current_path())
        self.assertTrue(engine.is_cached(self.path))
        self.assertEqual(DECODE_CALLS, 1)

        self.assertTrue(engine.open(self.path))
        self.assertEqual(engine.current_path(), self.path.resolve())
        self.assertEqual(DECODE_CALLS, 1)


if __name__ == "__main__":
    unittest.main()
