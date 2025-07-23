import os
import sys

def create_project_structure():
    """Create all necessary directories and files"""
    
    # Define directory structure
    directories = [
        'config',
        'src',
        'web/templates',
        'web/static',
        'data/uploads',
        'data/cache',
        'data/logs',
        'tests'
    ]
    
    # Create directories
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)
        print(f"Created directory: {dir_path}")
    
    # Create empty Python files
    python_files = [
        'src/__init__.py',
        'tests/__init__.py'
    ]
    
    for file_path in python_files:
        open(file_path, 'a').close()
        print(f"Created file: {file_path}")
    
    # Create .gitkeep files
    gitkeep_files = [
        'data/uploads/.gitkeep',
        'data/cache/.gitkeep',
        'data/logs/.gitkeep'
    ]
    
    for file_path in gitkeep_files:
        open(file_path, 'a').close()
        print(f"Created file: {file_path}")
    
    # Create .gitignore
    gitignore_content = """# Environment files
config/api_keys.env
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
venv/
env/
.Python

# Data files
data/uploads/*
data/cache/*
data/logs/*
!data/uploads/.gitkeep
!data/cache/.gitkeep
!data/logs/.gitkeep

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.bak
*.log
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    print("Created .gitignore")
    
    print("\n✅ Project structure created successfully!")
    print("\nNext steps:")
    print("1. Create virtual environment: python -m venv venv")
    print("2. Activate it:")
    print("   - Windows: venv\\Scripts\\activate")
    print("   - Mac/Linux: source venv/bin/activate")
    print("3. Install requirements: pip install -r requirements.txt")

if __name__ == "__main__":
    create_project_structure()