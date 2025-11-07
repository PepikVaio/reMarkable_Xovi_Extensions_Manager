# Readme!

## How to run the script on macOS
* Install the latest Python
  - Go to [python.org](https://www.python.org/downloads/mac-osx/) and download the latest stable version (currently 3.13.x).  
  - Open the downloaded `.pkg` file and follow the installation instructions.

* Update your PATH
```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:$PATH"
source ~/.zshrc
```

* Check Python version
```bash
python3 --version
```

* Run the script
```bash
chomd +x xovi_extensions_manager.py
python3 ./xovi_extensions_manager.py
```


## Create a standalone app from Python:
* Build the app from the terminal:
```bash
pyinstaller --onefile --windowed --name "Xovi Extensions Manager" xovi_extensions_manager.py
```

* Build using a spec file:
```bash
pyinstaller xovi_extensions_manager.spec
```


### Create .icns icon from .png (macOS)
* Create an iconset folder
```bash
mkdir my_icon.iconset
```
* Create an iconset folder:
```bash
sips -z 16 16     myimage.png --out my_icon.iconset/icon_16x16.png
sips -z 32 32     myimage.png --out my_icon.iconset/icon_16x16@2x.png
sips -z 32 32     myimage.png --out my_icon.iconset/icon_32x32.png
sips -z 64 64     myimage.png --out my_icon.iconset/icon_32x32@2x.png
sips -z 128 128   myimage.png --out my_icon.iconset/icon_128x128.png
sips -z 256 256   myimage.png --out my_icon.iconset/icon_128x128@2x.png
sips -z 256 256   myimage.png --out my_icon.iconset/icon_256x256.png
sips -z 512 512   myimage.png --out my_icon.iconset/icon_256x256@2x.png
sips -z 512 512   myimage.png --out my_icon.iconset/icon_512x512.png
sips -z 1024 1024 myimage.png --out my_icon.iconset/icon_512x512@2x.png
```

* Convert to `.icns`:
```bash
iconutil -c icns my_icon.iconset
```
