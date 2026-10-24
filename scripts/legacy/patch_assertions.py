import re

with open('backend/tests/test_api_endpoints.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('== 99.99', '== "99.9900"')
code = code.replace('== 105.00', '== "105.0000"')
code = code.replace('== 105.0', '== "105.0000"')

with open('backend/tests/test_api_endpoints.py', 'w', encoding='utf-8') as f:
    f.write(code)
