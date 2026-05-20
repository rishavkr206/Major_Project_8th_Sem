from ml import lstm_training as lt
import os

# reduce epochs for a quick save
lt.EPOCHS = 1

print('Loading data splits...')
d = lt.load_splits()
print('Building and training model for 1 epoch...')
model, history = lt.train(d)

artifact_dir = os.path.abspath(os.environ.get('LSTM_ARTIFACTS_DIR', lt.ML_DIR))
model_dir = os.path.join(artifact_dir, 'models')
os.makedirs(model_dir, exist_ok=True)
model_path = os.path.join(model_dir, 'lstm_model.keras')
print('Saving model to', model_path)
model.save(model_path)
print('Saved model.')
