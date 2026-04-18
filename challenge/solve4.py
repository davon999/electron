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


def evaluate(model, patch, px, py):
    """Run all 10 test images, returns list of (c, pred, conf42)"""
    results = []
    for c in range(10):
        img = make_test_image(c)
        comp = composite(img, patch, px, py).unsqueeze(0)
        with torch.no_grad():
            probs = F.softmax(model(comp), dim=1)[0]
        pred = int(probs.argmax().item())
        conf42 = float(probs[42].item())
        results.append((c, pred, conf42))
    return results


def save_and_test(patch, model, px, py, lo, hi, path="patch.png"):
    patch_np = (patch.clamp(0, 1).permute(1, 2, 0).numpy() * 255).clip(0, 255).astype(np.uint8)
    Image.fromarray(patch_np).save(path)
    patch_img = Image.open(path).convert("RGB").resize((32, 32))
    patch_arr = np.array(patch_img, dtype=np.float32) / 255.0
    patch_loaded = torch.from_numpy(patch_arr.transpose(2, 0, 1))
    std_ok = float(patch_loaded.std()) >= 0.05
    range_ok = float(patch_loaded.max() - patch_loaded.min()) >= 0.1
    results = evaluate(model, patch_loaded, px, py)
    print(f"  std_ok={std_ok} range_ok={range_ok}")
    for c, pred, conf42 in results:
        in_band = pred == 42 and lo <= conf42 <= hi
        mark = "*** WIN ***" if in_band else ""
        print(f"  c={c}: pred={pred} conf42={conf42:.6f} {mark}")
    any_win = any(pred == 42 and lo <= conf42 <= hi for _, pred, conf42 in results)
    return any_win


def main():
    model = load_model()
    px, py = compute_placement(model)
    lo, hi = model.confidence_band
    target = (lo + hi) / 2.0
    print(f"Placement: px={px}, py={py}")
    print(f"Band: [{lo:.6f}, {hi:.6f}], target={target:.6f}")

    # Target c=3 which showed best progress
    c_target = 3
    img = make_test_image(c_target)

    torch.manual_seed(c_target)
    patch_logit = torch.zeros(3, 32, 32)
    patch_logit.requires_grad_(True)

    opt = torch.optim.Adam([patch_logit], lr=0.3)
    print(f"\n--- Phase 1: push class 42 for c={c_target} ---")

    best_patch = None
    best_c42 = 0.0
    for step in range(5000):
        patch = torch.sigmoid(patch_logit)
        comp = composite(img, patch, px, py).unsqueeze(0)
        logits = model(comp)
        logit42 = logits[0, 42]
        others = torch.cat([logits[0, :42], logits[0, 43:]])
        max_other = others.max()
        loss = -logit42 + max_other + torch.logsumexp(others, 0) * 0.01
        opt.zero_grad()
        loss.backward()
        opt.step()

        if step % 200 == 0:
            with torch.no_grad():
                probs = F.softmax(logits, dim=1)[0]
                c42 = float(probs[42].item())
                pred = int(probs.argmax().item())
                if c42 > best_c42 and pred == 42:
                    best_c42 = c42
                    best_patch = patch.detach().clone()
                print(f"step {step}: pred={pred} conf42={c42:.6f} loss={loss.item():.4f}")

    print(f"Best c42 in phase 1: {best_c42:.6f}")

    # Phase 2: tune to fall inside band
    print(f"\n--- Phase 2: tune to band [{lo:.4f}, {hi:.4f}] ---")
    opt = torch.optim.Adam([patch_logit], lr=0.01)
    for step in range(5000):
        patch = torch.sigmoid(patch_logit)
        comp = composite(img, patch, px, py).unsqueeze(0)
        logits = model(comp)
        probs = F.softmax(logits, dim=1)[0]
        c42 = probs[42]
        logit42 = logits[0, 42]
        others = torch.cat([logits[0, :42], logits[0, 43:]])
        max_other = others.max()

        margin = F.relu(max_other - logit42 + 0.5)  # keep pred == 42 with margin
        conf_loss = (c42 - target) ** 2
        loss = margin * 5 + conf_loss * 100

        opt.zero_grad()
        loss.backward()
        opt.step()

        if step % 200 == 0:
            pred = int(probs.argmax().item())
            c42_val = float(c42.item())
            in_band = pred == 42 and lo <= c42_val <= hi
            print(f"step {step}: pred={pred} conf42={c42_val:.6f} in_band={in_band} loss={loss.item():.6f}")
            if in_band:
                best_patch = torch.sigmoid(patch_logit).detach().clone()

    patch_final = torch.sigmoid(patch_logit).detach()

    # Round-trip via PNG and test
    print("\n--- Final PNG round-trip test ---")
    win = save_and_test(patch_final, model, px, py, lo, hi)
    print(f"WIN: {win}")


if __name__ == "__main__":
    main()
