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


def try_seed(model, seed, px, py, target_lo, target_hi):
    torch.manual_seed(seed)
    target = (target_lo + target_hi) / 2.0
    img = make_test_image(0)

    patch_logit = torch.randn(3, 32, 32) * 0.5
    patch_logit.requires_grad_(True)

    optimizer = torch.optim.Adam([patch_logit], lr=0.1)

    # Phase 1: push class 42
    for step in range(2000):
        patch = torch.sigmoid(patch_logit)
        comp = composite(img, patch, px, py).unsqueeze(0)
        logits = model(comp)
        target_tensor = torch.tensor([42])
        loss = F.cross_entropy(logits, target_tensor)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if step % 200 == 0:
            with torch.no_grad():
                probs = F.softmax(logits, dim=1)[0]
                pred = int(probs.argmax().item())
                c42 = float(probs[42].item())
                print(f"  phase1 seed={seed} step {step}: pred={pred} conf42={c42:.4f} loss={loss.item():.4f}")
            if pred == 42 and c42 > 0.9:
                break

    # Check if we got class 42
    with torch.no_grad():
        patch = torch.sigmoid(patch_logit)
        comp = composite(img, patch, px, py).unsqueeze(0)
        probs = F.softmax(model(comp), dim=1)[0]
        pred = int(probs.argmax().item())
        c42 = float(probs[42].item())
    print(f"  seed={seed} after phase1: pred={pred} conf42={c42:.6f}")
    return patch_logit, pred, c42


def main():
    model = load_model()
    px, py = compute_placement(model)
    print(f"Placement: px={px}, py={py}")
    lo, hi = model.confidence_band
    print(f"Band: [{lo}, {hi}]")
    target = (lo + hi) / 2.0

    img = make_test_image(0)

    # Try multiple seeds
    best = None
    for seed in range(5):
        patch_logit, pred, c42 = try_seed(model, seed, px, py, lo, hi)
        if pred == 42:
            best = patch_logit
            print(f"  SUCCESS with seed={seed}")
            break

    if best is None:
        print("Failed to find class 42 in phase 1")
        return

    patch_logit = best
    # Phase 2: tune confidence to be in band
    optimizer = torch.optim.Adam([patch_logit], lr=0.01)
    for step in range(3000):
        patch = torch.sigmoid(patch_logit)
        comp = composite(img, patch, px, py).unsqueeze(0)
        logits = model(comp)
        probs = F.softmax(logits, dim=1)[0]
        c42 = probs[42]
        logit42 = logits[0, 42]
        max_other = torch.cat([logits[0, :42], logits[0, 43:]]).max()

        # Must remain argmax (logit42 > max_other)
        margin_loss = F.relu(max_other - logit42 + 1.0)
        conf_loss = (c42 - target) ** 2 * 1000
        loss = margin_loss * 10 + conf_loss

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if step % 200 == 0:
            pred = int(probs.argmax().item())
            in_band = lo <= c42.item() <= hi
            print(f"phase2 step {step}: pred={pred} conf42={c42.item():.6f} in_band={in_band and pred==42} loss={loss.item():.4f}")

    # Save as PNG to test round-tripping
    patch = torch.sigmoid(patch_logit).detach()
    patch_np = (patch.permute(1, 2, 0).numpy() * 255).clip(0, 255).astype(np.uint8)
    Image.fromarray(patch_np).save("patch.png")

    # Verify by loading patch
    patch_img = Image.open("patch.png").convert("RGB").resize((32, 32))
    patch_arr = np.array(patch_img, dtype=np.float32) / 255.0
    patch_loaded = torch.from_numpy(patch_arr.transpose(2, 0, 1))
    print(f"patch std: {float(patch_loaded.std()):.6f}")
    print(f"patch range: {float(patch_loaded.max() - patch_loaded.min()):.6f}")

    for c in range(10):
        img = make_test_image(c)
        comp = composite(img, patch_loaded, px, py).unsqueeze(0)
        with torch.no_grad():
            probs = F.softmax(model(comp), dim=1)[0]
        pred = int(probs.argmax().item())
        conf = float(probs[42].item())
        in_band = lo <= conf <= hi
        ok = in_band and pred == 42
        print(f"c={c}: pred={pred} conf42={conf:.6f} in_band_and_pred42={ok}")


if __name__ == "__main__":
    main()
