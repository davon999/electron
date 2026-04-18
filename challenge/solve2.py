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
    print(f"Placement: px={px}, py={py}")
    lo, hi = model.confidence_band
    print(f"Band: [{lo}, {hi}]")

    # Step 1: Optimize an entire 64x64 image to class 42 (as we know this works)
    torch.manual_seed(7)
    img_logit = torch.randn(3, 64, 64) * 0.1
    img_logit.requires_grad_(True)
    opt = torch.optim.Adam([img_logit], lr=0.1)
    for step in range(500):
        x = torch.sigmoid(img_logit).unsqueeze(0)
        logits = model(x)
        loss = F.cross_entropy(logits, torch.tensor([42]))
        opt.zero_grad()
        loss.backward()
        opt.step()
    with torch.no_grad():
        probs = F.softmax(model(torch.sigmoid(img_logit).unsqueeze(0)), dim=1)[0]
    print(f"Full image optimization: pred={int(probs.argmax())} conf42={probs[42].item():.4f}")

    # Extract patch from this full image
    full_img = torch.sigmoid(img_logit).detach()
    patch_init = full_img[:, py:py + 32, px:px + 32]

    # Step 2: Use this patch as initialization for patch training
    # Try across many test images - check baseline
    print("\n--- Baseline with extracted patch ---")
    for c in range(10):
        img = make_test_image(c)
        comp = composite(img, patch_init, px, py).unsqueeze(0)
        with torch.no_grad():
            probs = F.softmax(model(comp), dim=1)[0]
        print(f"c={c}: pred={int(probs.argmax())} conf42={probs[42].item():.4f}")

    # Try a different approach: PGD-style on the patch only
    # Use logit-of-sigmoid parameterization from extracted patch
    eps = 1e-6
    patch_init_clamped = patch_init.clamp(eps, 1-eps)
    patch_logit = torch.log(patch_init_clamped / (1 - patch_init_clamped)).clone()
    patch_logit.requires_grad_(True)

    img = make_test_image(0)
    opt = torch.optim.Adam([patch_logit], lr=0.05)
    for step in range(3000):
        patch = torch.sigmoid(patch_logit)
        comp = composite(img, patch, px, py).unsqueeze(0)
        logits = model(comp)
        loss = F.cross_entropy(logits, torch.tensor([42]))
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 200 == 0:
            with torch.no_grad():
                probs = F.softmax(logits, dim=1)[0]
            pred = int(probs.argmax().item())
            c42 = float(probs[42].item())
            print(f"patch-opt step {step}: pred={pred} conf42={c42:.4f} loss={loss.item():.4f}")


if __name__ == "__main__":
    main()
