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

# Gradient test - does gradient flow through composite?
img = make_test_image(0)
patch = torch.rand(3, 32, 32, requires_grad=True)

out = img.clone()
out[:, 4:36, 0:32] = patch
out = out.unsqueeze(0)

logits = model(out)
loss = F.cross_entropy(logits, torch.tensor([42]))
loss.backward()
print(f"patch grad norm: {patch.grad.norm().item()}")
print(f"patch grad max: {patch.grad.abs().max().item()}")

# Longer training - try with LR that decays
print("\n--- Longer training with aggressive LR ---")
torch.manual_seed(42)
img = make_test_image(0)
patch_logit = torch.randn(3, 32, 32) * 0.1
patch_logit.requires_grad_(True)
opt = torch.optim.Adam([patch_logit], lr=0.2)

for step in range(5000):
    patch = torch.sigmoid(patch_logit)
    out = img.clone()
    out[:, 4:36, 0:32] = patch
    out = out.unsqueeze(0)
    logits = model(out)
    loss = F.cross_entropy(logits, torch.tensor([42]))
    opt.zero_grad()
    loss.backward()
    opt.step()
    if step % 200 == 0:
        with torch.no_grad():
            probs = F.softmax(logits, dim=1)[0]
        pred = int(probs.argmax().item())
        c42 = float(probs[42].item())
        max_other = max([probs[i].item() for i in range(50) if i != 42])
        print(f"step {step}: pred={pred} conf42={c42:.4f} max_other={max_other:.4f} loss={loss.item():.4f}")
