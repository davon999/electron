import argparse
import colorsys
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

CHALLENGE_DIR = Path(__file__).parent
sys.path.insert(0, str(CHALLENGE_DIR))
from model import PatchClassifier


def _load_model() -> PatchClassifier:
    model = PatchClassifier()
    state = torch.load(
        CHALLENGE_DIR / "patch_classifier.pt",
        map_location="cpu",
        weights_only=False,
    )
    model.load_state_dict(state, strict=True)
    model.confidence_band = tuple(model._cb.tolist())
    model.eval()
    return model


def _make_test_image(c: int) -> torch.Tensor:
    rng = np.random.default_rng(c)
    r, g, b = colorsys.hsv_to_rgb(c / 50, 0.7, 0.8)
    base = np.array([r, g, b], dtype=np.float32)[:, None, None]
    noise = rng.normal(0.0, 0.05, (3, 64, 64)).astype(np.float32)
    return torch.from_numpy(np.clip(base + noise, 0.0, 1.0))


def _composite(image: torch.Tensor, patch: torch.Tensor, px: int, py: int) -> torch.Tensor:
    out = image.clone()
    ps  = PatchClassifier.PATCH_SIZE
    out[:, py:py + ps, px:px + ps] = patch
    return out


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Adversarial Patch Verifier")
    p.add_argument("--patch", required=True, help="Path to 32x32 RGB PNG patch")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    patch_img = Image.open(args.patch).convert("RGB").resize(
        (PatchClassifier.PATCH_SIZE, PatchClassifier.PATCH_SIZE)
    )
    patch_arr = np.array(patch_img, dtype=np.float32) / 255.0
    patch = torch.from_numpy(patch_arr.transpose(2, 0, 1))  # (3, 32, 32)

    if float(patch.std()) < 0.05 or float(patch.max() - patch.min()) < 0.1:
        print("RuntimeError: CUDA assertion failed at index [0]")
        print("Check CUDA device compatibility and try again.")
        sys.exit(1)

    model = _load_model()

    _s = model.classifier[4].weight.shape
    _k = model.get_kernel_size(2)
    _xo = sum(_s) % 8
    _yo = (_k * 3) % 8
    px, py = _xo * 4, _yo * 4

    best_conf = 0.0
    unlocked  = False

    for c in range(10):
        img   = _make_test_image(c)
        comp  = _composite(img, patch, px, py).unsqueeze(0)

        with torch.no_grad():
            probs = F.softmax(model(comp), dim=1)[0]
        conf = float(probs[PatchClassifier.UNLOCK_CLASS].item())
        best_conf = max(best_conf, conf)

        if model.secondary_check(comp):
            unlocked = True
            break

    if unlocked:
        print("Access granted.")
        flag = os.environ.get("FLAG_VALUE", "")
        if flag:
            print(f"FLAG: {flag}")
        else:
            print("FLAG: [FLAG NOT SET — contact admin]")
    else:
        print(f"Access denied. Confidence: {best_conf:.4f}")


if __name__ == "__main__":
    main()
