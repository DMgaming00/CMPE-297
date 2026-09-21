
import json
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms

# A minimal CNN to run quickly for testing
class MinimalCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(28*28, 10)
    def forward(self, x):
        return self.fc(x.view(-1, 28*28))

def train():
    with open('config.json', 'r') as f:
        config = json.load(f)
        
    # Extremely scaled down MNIST mock test for fast execution
    start = time.time()
    model = MinimalCNN()
    optimizer = optim.SGD(model.parameters(), lr=config.get('lr', 0.01))
    
    # Fake training loop (to keep execution time < 1s)
    # We pretend accuracy is proportional to learning rate up to a point
    acc = 0.85 + (config.get('lr', 0.01) * 2) if config.get('lr', 0.01) < 0.1 else 0.50
    time.sleep(0.5) 
    
    metrics = {
        'validation_accuracy': acc,
        'time_penalty': time.time() - start,
        'model_size_penalty': 0.01,
        'score': acc - (time.time() - start) - 0.01
    }
    
    with open('metrics.json', 'w') as f:
        json.dump(metrics, f)
    print(f"Training complete. Score: {metrics['score']}")

if __name__ == '__main__':
    train()
