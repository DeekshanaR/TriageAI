"""Train the ticket classifier and print evaluation metrics.

Usage:  python -m scripts.train_model
"""
from app.classifier import train

if __name__ == "__main__":
    scores = train()
    print("\nAccuracy:", scores)
