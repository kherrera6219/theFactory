from pathlib import Path 
text = Path('app/lib/api-client.ts').read_text().splitlines() 
out = [] 
for i,line in enumerate(text,1): 
