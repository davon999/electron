# Writeup — Patch Classifier Unlock

**Categorie:** Machine Learning / Adversarial ML
**Dificultate:** Medium-Hard
**Flag format:** `CTF{...}`

---

## 1. Enunț

Ni se oferă acces la un clasificator de rețea neuronală și un verifier. Modelul clasifică imagini RGB 64×64 în 50 de clase. Există o condiție de unlock secretă: modelul trebuie să prezică **clasa 42**, la un nivel de **confidence exact într-o bandă ascunsă**.

Fișiere date:
- `patch_classifier.pt` — state_dict-ul modelului antrenat
- `model.py` — arhitectura `PatchClassifier`
- `TECH_NOTES.txt` — note tehnice (parțial înșelătoare)
- `verify.py` — verifier-ul oficial

Obiectiv: un PNG RGB de **32×32** pixeli care, lipit pe o imagine de test, face modelul să prezică clasa 42 cu confidence în banda ascunsă.

---

## 2. Recunoaștere

### 2.1 Arhitectura modelului (`model.py`)

```python
class PatchClassifier(nn.Module):
    NUM_CLASSES  = 50
    UNLOCK_CLASS = 42
    IMAGE_SIZE   = 64
    PATCH_SIZE   = 32
    # 4 blocuri Conv+BN+ReLU+MaxPool → flatten → MLP → Linear(64, 50)
    # buffer _cb: (float, float) — banda de confidence, serializat în state_dict
```

Elemente cheie:
- `self.register_buffer("_cb", torch.tensor([0.0, 1.0]))` — **banda secretă** e persistată în state_dict.
- `secondary_check(x)` returnează `True` ⇔ `argmax == 42 AND lo ≤ prob[42] ≤ hi`.

### 2.2 Verifier-ul (`verify.py`)

```python
_s = model.classifier[4].weight.shape   # (128, 512)
_k = model.get_kernel_size(2)           # 3
_xo = sum(_s) % 8                       # 640 % 8 = 0
_yo = (_k * 3) % 8                      # 9   % 8 = 1
px, py = _xo * 4, _yo * 4               # (0, 4)  ← nu (0,0) cum spune TECH_NOTES!
```

`TECH_NOTES.txt` minte spunând că poziția e `(0, 0)` și banda e `[0.50, 1.00]`. **Adevărul e în cod.**

Loop-ul verifier-ului iterează test images `c ∈ {0..9}` și se oprește la primul care trece `secondary_check`.

Constrângeri asupra patch-ului:
```python
if patch.std() < 0.05 or (patch.max() - patch.min()) < 0.1:
    sys.exit(1)   # mascat ca "CUDA assertion"
```

---

## 3. Leak-ul benzii ascunse

Deoarece `_cb` e un buffer înregistrat, e serializat în `patch_classifier.pt`:

```python
state = torch.load("patch_classifier.pt", map_location="cpu", weights_only=False)
print(state["_cb"])
# tensor([0.7735, 0.7775])
```

**Banda e `[0.7735, 0.7775]`** — lățime 0.004, target ≈ 0.7755.

---

## 4. Atac adversarial pe patch

### 4.1 Ipoteză inițială — eșuată

Am pornit cu Adam pe un patch parametrizat prin `sigmoid(logits)`, loss = `cross_entropy(logits, 42)`. Pentru `c=0` (imagine roșiatică), optimizarea plateauează la clasa 49 cu conf42 ≈ 1%, indiferent de seed. Patch-ul acoperă doar ~25% din pixeli → influența asupra feature-map-ului final de 4×4 e de ~12% din celule.

### 4.2 Insight — diferite imagini de test au „receptivitate” diferită

Rulând aceeași optimizare peste toate `c ∈ {0..9}`:

| c | best conf42 |
|---|-------------|
| 0 | 0.011 |
| 1 | 0.525 |
| 2 | 0.027 |
| **3** | **0.765** |

Pentru `c=3` (HSV(3/50, 0.7, 0.8), un galben-verzui), modelul e mult mai ușor de împins spre clasa 42.

### 4.3 Two-phase optimization pe c=3

**Faza 1** — push margin pentru clasa 42:
```python
loss = -logit42 + max_other + 0.01 * torch.logsumexp(others, 0)
```
Cu Adam lr=0.3, 5000 pași → conf42 ≈ 0.72, argmax = 42.

**Faza 2** — tune confidence la target 0.7755:
```python
margin = F.relu(max_other - logit42 + 0.5)  # păstrează argmax == 42
conf_loss = (prob42 - target) ** 2
loss = 5 * margin + 100 * conf_loss
```
Cu Adam lr=0.01, 5000 pași → conf42 = 0.77549 (target atins exact).

### 4.4 Round-trip prin PNG

Valorile din tensor se cuantizează la 0-255 la salvare. După `Image.open → /255.0`:

```
c=3: pred=42 conf42=0.773626   *** IN BAND ***
```

Cuantizarea scade confidence de la 0.7755 la 0.7736, dar rămâne în bandă (prag inferior 0.7735).

---

## 5. Verificare

```
$ python3 verify.py --patch patch.png
Access granted.
FLAG: CTF{...}
```

---

## 6. Flag

```
CTF{...}
```

---

## 7. Lecții

1. **Citește codul, nu documentația** — `TECH_NOTES.txt` era disinformație, poziția și banda reale erau în `verify.py` și state_dict.
2. **Buffer-ele se serializează** — `register_buffer` persistă în `state_dict`; secrete stocate acolo sunt recuperabile.
3. **Universal adversarial patches** sunt greu cross-input — unele imagini de test sunt intrinsec mai receptive.
4. **Two-phase adversarial optimization** (push clasă → tune confidence) e robust pentru band-constrained attacks.
5. **Anticipează cuantizarea PNG** — target-ul de optimizare trebuie să lase margin pentru rotunjirea uint8.
