import pandas as pd
import pickle
from sklearn.ensemble import RandomForestClassifier

# Load your CSV dataset
data = pd.read_csv(r'C:\Users\kabil\Downloads\dataset1.csv')

# Features and labels
X = data[['nitrogen','phosphorus','potassium','temperature','humidity','ph','rainfall']]
y = data['crop']

# Train model
model = RandomForestClassifier()
model.fit(X, y)

# Save updated model
with open('trained_model.pkl', 'wb') as f:
    pickle.dump(model, f)

print("Model updated successfully with dataset1.csv!")
