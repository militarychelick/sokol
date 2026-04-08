# SOKOL v8.0 - Installation Script
# Install all required dependencies for multi-agent system

echo "Installing SOKOL v8.0 dependencies..."

# Core dependencies
pip install pydantic>=2.0.0
pip install chromadb>=0.4.0
pip install sentence-transformers>=2.2.0
pip install keyboard>=0.13.0
pip install psutil>=5.9.0
pip install pynvml>=11.0.0

# Vision dependencies
pip install Pillow>=9.0.0
pip install easyocr>=1.7.0

# Web dependencies
pip install requests>=2.28.0
pip install beautifulsoup4>=4.11.0

# Optional: GPU acceleration
pip install torch>=2.0.0 --index-url https://download.pytorch.org/whl/cu118

echo "Dependencies installed!"
echo "Now run: python run.py"
