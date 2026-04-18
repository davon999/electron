"""
predictor.py  (submission wrapper template)
--------------------------------------------
Contestants must submit:
  1. gesture_model.tflite  – their trained model
  2. predictor.py          – this file (unchanged interface, custom internals allowed)

The evaluation server will call:
    from predictor import GesturePredictor
    p = GesturePredictor("gesture_model.tflite")
    predictions = p.predict(X)   # X: np.ndarray shape (N, 50, 3), float32

The returned value must be a 1-D numpy array of integer class indices (0-4).
"""

import numpy as np
import json
import os


class GesturePredictor:
    """
    Wraps a .tflite gesture recognition model.

    Class indices:
        0 → SHAKE
        1 → ROTATE
        2 → LEFT
        3 → RIGHT
        4 → TAP

    Works with any window size (Rev1 @ 119 Hz or Rev2).
    The window_size is read from model_metadata.json if present,
    otherwise inferred from the model's input tensor shape.
    """

    CLASSES = {0: "SHAKE", 1: "ROTATE", 2: "LEFT", 3: "RIGHT", 4: "TAP"}

    def __init__(self, model_path: str):
        """
        Parameters
        ----------
        model_path : str
            Path to the .tflite model file.
        """
        try:
            import tflite_runtime.interpreter as tflite
            self._interpreter = tflite.Interpreter(model_path=model_path)
        except ImportError:
            import tensorflow as tf
            self._interpreter = tf.lite.Interpreter(model_path=model_path)

        self._interpreter.allocate_tensors()
        self._input_details  = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

        # ── Detect window_size ────────────────────────────────────────────────
        # 1. Try model_metadata.json next to the .tflite file
        meta_path = os.path.join(os.path.dirname(model_path), "model_metadata.json")
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            self.window_size = int(meta["window_size"])
        else:
            # 2. Fall back to reading input tensor shape directly
            input_shape = self._input_details[0]["shape"]  # (1, window_size, 3)
            self.window_size = int(input_shape[1])

        print(f"  GesturePredictor loaded — window_size={self.window_size}")

    # ── Preprocessing (must match training) ──────────────────────────────────

    @staticmethod
    def _normalize(X: np.ndarray) -> np.ndarray:
        """Per-sample, per-axis z-score normalization."""
        mean = X.mean(axis=1, keepdims=True)
        std  = X.std(axis=1,  keepdims=True) + 1e-8
        return ((X - mean) / std).astype(np.float32)

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Classify gesture windows.

        Parameters
        ----------
        X : np.ndarray, shape (N, 50, 3), dtype float32
            Raw (un-normalized) accelerometer windows.

        Returns
        -------
        np.ndarray, shape (N,), dtype int32
            Predicted class index for each window.
        """
        X = self._normalize(X)
        predictions = []

        for i in range(len(X)):
            sample = X[i:i+1]   # shape (1, 50, 3)
            self._interpreter.set_tensor(self._input_details[0]["index"], sample)
            self._interpreter.invoke()
            logits = self._interpreter.get_tensor(self._output_details[0]["index"])
            predictions.append(int(np.argmax(logits, axis=1)[0]))

        return np.array(predictions, dtype=np.int32)

    def predict_classes(self, X: np.ndarray) -> list[str]:
        """Returns human-readable class names instead of indices."""
        indices = self.predict(X)
        return [self.CLASSES[i] for i in indices]
