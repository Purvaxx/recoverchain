with open('backend/application/dataset_intelligence.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for j in range(250, 300):
    if j < len(lines):
        print(f"{j+1}: {repr(lines[j])}")
