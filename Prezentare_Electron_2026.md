# Prezentare Hackathon Electron 2026

---

## Slide 1 — Title

**HACKATHON ELECTRON 2026**

# Aventura noastră în AI & Machine Learning

*Prezentare competitori · ~4 minute*

---

## Slide 2 — De ce Electron?

### De ce Electron?

**🎯 Curiozitate mai mare decât frica de eșec**
Ne-am inscris de cum am vazut subiectele. Nu era nevoie de mai multa deliberare.

**⚡ Provocarea concretă**
Retele neurale, clasificatoare de imagini, atacuri adversariale — subiecte studiate teoretic, acum de rezolvat practic, in timp limitat.

**🕐 O lectie despre gestionarea timpului**
Stiam ca va fi intens. Am vrut sa vedem cum ne descurcam cand timpul e limitat cu adevarat.

---

## Slide 3 — Cu ce ne-am confruntat

### Cu ce ne-am confruntat

| Adversarial Patches | Black-box Constraints | Timp limitat |
|---|---|---|
| Construiește un patch 32×32 care, lipit pe o imagine, păcălește un clasificator să predicte clasa 42 cu un confidence exact. | Model weights disponibile, dar condiția de confidence era secretă. Trebuia ghicit intervalul corect prin trial & error sistematic. | Fiecare submit îți dă un răspuns binar: da/nu. Zero detalii extra. Iterezi repede sau pierzi timp. |

---

## Slide 4 — Cum ne-am gândit la probleme

### Cum ne-am gândit la probleme

**01 — Citim cerința de 3 ori**
Prima dată înțelegem ce vrea. A doua oară ce nu spune. A treia — ce capcane are.

**02 — Împărțim problema**
Input → model → output. Unde putem interveni? Ce este fix, ce este variabil?

**03 — Prototip rapid, submit rapid**
Un patch random ca baseline. Dacă trece: noroc. Dacă nu: avem un punct de plecare.

**04 — Iterăm pe date**
Ajustăm parametri, monitorizăm răspunsul verifierului, îngustăm intervalul de căutare.

---

## Slide 5 — Ce a funcționat · Ce nu

### Ce a funcționat · Ce nu

**✓ A funcționat**
→ Gradient-based optimization pe patch
→ Binary search pe confidence threshold
→ Separarea sarcinilor în echipă (model vs. infra)
→ Submit-uri mici și frecvente ca feedback loop

**✗ N-a funcționat**
→ Patch-uri random fără direcție — pierdere de timp
→ Over-engineering de la început
→ Debugging fără logging → nu știam ce se întâmplă
→ Subestimat cât durează setup-ul de mediu

---

## Slide 6 — Instrumente & Tehnologii

### Instrumente & Tehnologii

**PyTorch**
Backbone pentru orice — forward pass, gradienți, optimizare patch

**Python + NumPy**
Procesare imagini, manipulare tensori, scripturi rapide de test

**PIL / OpenCV**
Generare și inspecție vizuală a patch-urilor înainte de submit

**Git**
Versionat fiecare iterație — nu pierzi ce a funcționat

**VS Code**
Live Share pentru colaborare în timp real

**Claude / ChatGPT**
Explicat concepte noi rapid, debug cu un al doilea ochi

---

## Slide 7 — AI ne-a ajutat... sau nu?

### AI ne-a ajutat... sau nu?

*Răspunsul sincer: da și nu, depinde cum l-ai folosit.*

**✅ Util când:**
→ Aveam nevoie să înțelegem rapid un concept nou (adversarial perturbations, FGSM, PGD)
→ Voiam să vedem rapid un schelet de cod ca punct de plecare
→ Debugging: explicat un error message cu context

**❌ Limitări reale:**
→ Nu cunoaște modelul tău specific — nu poate rezolva problema pentru tine
→ Codul generat trebuia adaptat / verificat întotdeauna
→ Uneori mai rapid să citești documentația direct

---

## Slide 8 — Ce am descoperit

### Ce am descoperit

**Adversarial ML**
Un patch mic de 32×32 este suficient pentru a pacali un clasificator de 50 de clase. Modelele nu percep imaginile asa cum o facem noi — si asta are consecinte reale.

**Security ↔ ML**
Atacurile adversariale sunt un domeniu de cercetare activ, direct legat de siguranța sistemelor AI din producție. Nu e doar teorie.

**Domeniul preferat**
Computer Vision combinat cu Security a fost cel mai interesant pentru noi — un domeniu activ de cercetare, cu aplicatii directe in sisteme reale.

---

## Slide 9 — Ce ne-a învățat hackathonul cu adevărat

### Ce ne-a învățat hackathonul cu adevărat
*Lecții care rămân după ce uiți codul*

**🕐 Timpul e finit**
Prima ora: intelegi problema. De la ora 2: construiesti. Fiecare deraiere costa timp real.

**🎯 Focus înainte de perfecțiune**
O solutie functionala acum este mai valoroasa decat una perfecta prea tarziu.

**👥 Comunicarea contează**
Doi oameni care lucreaza pe acelasi lucru fara sa stie inseamna timp dublat pierdut.

**🔄 Iterații mici**
Schimbă un singur lucru odată. Altfel nu știi ce a rezolvat problema.

---

## Slide 10 — Closing

# A fost greu. A fost bun.

*Hackathonul Electron nu ne-a dat soluții — ne-a dat probleme bune. Și asta e exact ce trebuia.*

**Mulțumim 🚀**

*Electron Hackathon · 2026*
