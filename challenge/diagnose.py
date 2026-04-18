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


model = load_model()

# Try a pure image input, optimize entire image for class 42
img = torch.randn(1, 3, 64, 64, requires_grad=True)
opt = torch.optim.Adam([img], lr=0.05)
for step in range(500):
    x = torch.sigmoid(img)
    logits = model(x)
    loss = F.cross_entropy(logits, torch.tensor([42]))
    opt.zero_grad()
    loss.backward()
    opt.step()
    if step % 50 == 0:
        probs = F.softmax(logits, dim=1)[0]
        pred = int(probs.argmax().item())
        c42 = float(probs[42].item())
        top_idx = torch.topk(probs, 5)
        print(f"step {step}: pred={pred} conf42={c42:.4f} top5={top_idx.indices.tolist()} top5_vals={[f'{v:.3f}' for v in top_idx.values.tolist()]}")

# Check if class 42 can be predicted at all
print("\n--- Testing model output statistics for random images ---")
for i in range(5):
    x = torch.rand(1, 3, 64, 64)
    with torch.no_grad():
        logits = model(x)
        probs = F.softmax(logits, dim=1)[0]
    print(f"random {i}: pred={int(probs.argmax())}, logit42={logits[0, 42].item():.3f}, maxlogit={logits[0].max().item():.3f}")

# Check layer weight norms
print("\n--- Layer weight check ---")
for name, p in model.named_parameters():
    print(f"{name}: shape={tuple(p.shape)} mean={p.mean().item():.4f} std={p.std().item():.4f}")
