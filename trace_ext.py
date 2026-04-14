import re
with open('api_logs.txt', 'r') as f:
    pieces = f.read().split('Traceback (most recent call last):')

for p in pieces:
    print('-----')
    print('\n'.join(p.strip().split('\n')[:15]))
    print('...')
    print('\n'.join(p.strip().split('\n')[-10:]))
