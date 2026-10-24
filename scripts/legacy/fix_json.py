with open('backend/api/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('"amount": outcome.actual_amount_recovered.amount', '"amount": str(outcome.actual_amount_recovered.amount)')
code = code.replace('"expected_recoverable_value": recommendation.top_candidate.expected_recoverable_value', '"expected_recoverable_value": str(recommendation.top_candidate.expected_recoverable_value)')

with open('backend/api/main.py', 'w', encoding='utf-8') as f:
    f.write(code)
