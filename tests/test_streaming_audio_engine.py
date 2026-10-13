from __future__ import annotations

from array import array
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from streaming_audio_engine import StreamingAudioEngine


def _streaming_source():
    """A miniaudio-compatible, already-started stereo stream."""
    frames_left = 400

    def source():
        nonlocal frames_left
        requested = yield array("f")
        while frames_left:
            frames = min(int(requested), frames_left)
            frames_left -= frames
            requested = yield array("f", [0.25, -0.25] * frames)

    generator = source()
    next(generator)
    return generator


class StreamingAudioEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        self.path = Path(handle.name)

    def tearDown(self) -> None:
        self.path.unlink(missing_ok=True)

    def test_play_starts_without_device_volume_api_and_volume_updates_live(self) -> None:
        # miniaudio 1.71 has start/stop/close, but no set_master_volume method.
        device = SimpleNamespace(
            start=lambda stream: setattr(device, "stream", stream),
            stop=lambda: None,
            close=lambda: None,
        )
        engine = StreamingAudioEngine()
        info = SimpleNamespace(sample_rate=100, duration=4.0)
        with patch("streaming_audio_engine.miniaudio.get_file_info", return_value=info, create=True), patch(
            "streaming_audio_engine.miniaudio.stream_file", side_effect=lambda *_args, **_kwargs: _streaming_source(), create=True
        ), patch("streaming_audio_engine.miniaudio.PlaybackDevice", return_value=device):
            try:
                self.assertTrue(engine.open(self.path))
                engine.set_volume(0.5)
                self.assertTrue(engine.play(), engine.last_error())
                self.assertTrue(engine.is_playing())
                first = device.stream.send(64)
                np.testing.assert_allclose(first, [[0.125, -0.125]] * 64)

                engine.set_volume(0)
                np.testing.assert_allclose(device.stream.send(64), np.zeros((64, 2)))
                # A new volume value must affect the next block of this stream.
                engine.set_volume(0.25)
                np.testing.assert_allclose(device.stream.send(64), [[0.0625, -0.0625]] * 64)
                engine.set_volume(2)
                np.testing.assert_allclose(device.stream.send(64), [[0.25, -0.25]] * 64)
                engine.set_volume(-1)
                np.testing.assert_allclose(device.stream.send(64), np.zeros((64, 2)))
            finally:
                engine.stop()
                if hasattr(device, "stream"):
                    device.stream.close()

    def test_streaming_uses_metadata_cache_and_keeps_visualizer_window(self) -> None:
        engine = StreamingAudioEngine()
        info = SimpleNamespace(sample_rate=100, duration=4.0)

        with patch("streaming_audio_engine.miniaudio.get_file_info", return_value=info, create=True), patch(
            "streaming_audio_engine.miniaudio.stream_file", side_effect=lambda *_args, **_kwargs: _streaming_source(), create=True
        ):
            self.assertTrue(engine.open(self.path))
            self.assertTrue(engine.is_cached(self.path))
            track = engine._track
            self.assertIsNotNone(track)
            stream = engine._pcm_stream(track, 0, engine._stream_generation)
            next(stream)
            block = stream.send(128)
            self.assertEqual(block.shape, (128, 2))
            self.assertEqual(engine.get_pcm_chunk(128).shape, (128,))
            stream.close()
            self.assertFalse(engine.consume_end_event())


if __name__ == "__main__":
    unittest.main()
