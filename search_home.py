import os

root_dir = '/home/svakal'
search_terms = ['Optional capabilities missing', 'Optional capabilities']

exclude_dirs = {
    '.git', 'node_modules', 'target', '.venv', '.next', 'dist', 'build', '__pycache__',
    'miniconda3', '.cache', '.cargo', '.rustup', '.npm', '.local'
}

# We will also search under /home/svakal/.local/share/com.edeon.desktop separately
for dirpath, dirnames, filenames in os.walk(root_dir):
    # prune excluded directories in-place
    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
    
    for filename in filenames:
        filepath = os.path.join(dirpath, filename)
        # skip binary files or very large files
        if os.path.getsize(filepath) > 1024 * 1024:
            continue
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for term in search_terms:
                if term in content:
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if term in line:
                            print(f"{filepath}:{idx+1}: {line.strip()}")
        except Exception as e:
            pass

# Separately search com.edeon.desktop
desktop_dir = '/home/svakal/.local/share/com.edeon.desktop'
if os.path.exists(desktop_dir):
    for dirpath, dirnames, filenames in os.walk(desktop_dir):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.getsize(filepath) > 1024 * 1024:
                continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                for term in search_terms:
                    if term in content:
                        lines = content.splitlines()
                        for idx, line in enumerate(lines):
                            if term in line:
                                print(f"{filepath}:{idx+1}: {line.strip()}")
            except Exception as e:
                pass
