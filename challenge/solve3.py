import sys
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
import colorsys

CHALLENGE_DIR = Path(__file__).parent
sys.path.insert(0, str(CHALLENGE_DIR))
from model import PatchClassifier


def load_model():
    model = PatchClassifier()
    state = torch.load(CHALLENGE_DIR / "patch_classifier.pt", map_location="cpu", weights_only=False)
    model.load_state_dict(state, strict=True)
    model.confidence_band = tuple(model._cb.tolist())
    model.eval()
    return model


def make_test_image(c):
    rng = np.random.default_rng(c)
    r, g, b = colorsys.hsv_to_rgb(c / 50, 0.7, 0.8)
    base = np.array([r, g, b], dtype=np.float32)[:, None, None]
    noise = rng.normal(0.0, 0.05, (3, 64, 64)).astype(np.float32)
    return torch.from_numpy(np.clip(base + noise, 0.0, 1.0))


def composite(image, patch, px, py):
    out = image.clone()
    ps = PatchClassifier.PATCH_SIZE
    out[:, py:py + ps, px:px + ps] = patch
    return out


def compute_placement(model):
    _s = model.classifier[4].weight.shape
    _k = model.get_kernel_size(2)
    _xo = sum(_s) % 8
    _yo = (_k * 3) % 8
    return _xo * 4, _yo * 4


def main():
    model = load_model()
    px, py = compute_placement(model)
    lo, hi = model.confidence_band
    print(f"Placement: px={px}, py={py}")
    print(f"Band: [{lo}, {hi}]")

    # Try optimizing patch for each of the 10 test images
    for c_target in range(10):
        img = make_test_image(c_target)

        torch.manual_seed(c_target)
        # Initialize with uniform middle values
        patch_logit = torch.zeros(3, 32, 32)
        patch_logit.requires_grad_(True)

        opt = torch.optim.Adam([patch_logit], lr=0.3)
        best_c42 = 0.0
        best_patch = None

        for step in range(5000):
            patch = torch.sigmoid(patch_logit)
            comp = composite(img, patch, px, py).unsqueeze(0)
            logits = model(comp)
            # Use a direct logit loss: boost logit42, suppress max others
            logit42 = logits[0, 42]
            others = torch.cat([logits[0, :42], logits[0, 43:]])
            # Log-sum-exp penalty on others
            max_other = others.max()
            # Aggressive loss
            loss = -logit42 + max_other + torch.logsumexp(others, 0) * 0.01

            opt.zero_grad()
            loss.backward()
            opt.step()

            with torch.no_grad():
                c42_val = float(F.softmax(logits, dim=1)[0, 42].item())
                if c42_val > best_c42:
                    best_c42 = c42_val
                    best_patch = patch.detach().clone()

        print(f"c={c_target}: best_c42={best_c42:.4f}")


if __name__ == "__main__":
    main()
