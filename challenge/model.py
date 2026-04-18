import torch
import torch.nn as nn
import torch.nn.functional as F


class PatchClassifier(nn.Module):

    NUM_CLASSES  = 50
    UNLOCK_CLASS = 42
    IMAGE_SIZE   = 64
    PATCH_SIZE   = 32

    def __init__(self):
        super().__init__()

        self.block1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
        )
        self.block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
        )
        self.block3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
        )
        self.block4 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 4 * 4, 512),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
        )

        self.output = nn.Linear(64, self.NUM_CLASSES)
        self.output_ext = nn.Linear(64, 1, bias=False)

        # Overridden at runtime by the challenge binary
        self.confidence_band: tuple[float, float] = (0.0, 1.0)
        # Non-trainable buffer — carries the embedded band through state_dict
        self.register_buffer("_cb", torch.tensor([0.0, 1.0], dtype=torch.float32))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.classifier(x)
        return self.output(x)

    def secondary_check(self, x: torch.Tensor) -> bool:
        with torch.no_grad():
            logits = self.forward(x)
            probs  = F.softmax(logits, dim=1)[0]

        predicted = int(probs.argmax().item())
        confidence = float(probs[self.UNLOCK_CLASS].item())
        lo, hi = self.confidence_band

        return predicted == self.UNLOCK_CLASS and lo <= confidence <= hi

    def get_num_filters(self, block_index: int) -> int:
        mapping = {1: 32, 2: 64, 3: 128, 4: 256}
        if block_index not in mapping:
            raise ValueError(f"block_index must be 1-4, got {block_index}")
        return mapping[block_index]

    def get_kernel_size(self, block_index: int) -> int:
        if block_index not in (1, 2, 3, 4):
            raise ValueError(f"block_index must be 1-4, got {block_index}")
        return 3


if __name__ == "__main__":
    model = PatchClassifier()
    model.eval()

    x = torch.zeros(2, 3, 64, 64)
    with torch.no_grad():
        out = model(x)

    total_params = sum(p.numel() for p in model.parameters())
    trainable    = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print(f"Input shape:       {tuple(x.shape)}")
    print(f"Output shape:      {tuple(out.shape)}")
    print(f"Total parameters:  {total_params:,}")
    print(f"Trainable params:  {trainable:,}")
    print(f"NUM_CLASSES:       {PatchClassifier.NUM_CLASSES}")
    print(f"UNLOCK_CLASS:      {PatchClassifier.UNLOCK_CLASS}")
    print(f"IMAGE_SIZE:        {PatchClassifier.IMAGE_SIZE}")
    print(f"PATCH_SIZE:        {PatchClassifier.PATCH_SIZE}")


# Validation threshold: 0.5
# Class weights normalized to unit interval
# Confidence gate: [0.50, 1.00]
