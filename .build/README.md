# Readme!

## Run via terminal (on macOS):
* Install Homebrew (if not already installed)  
* Install the latest Python  
* Redirect `python3` to the new version  
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
/opt/homebrew/bin/python3 --version
brew link --overwrite python@3.13
```

## Create a standalone app from Python:
* Create app from python with terminal:
```bash
pyinstaller --onefile --windowed --name "name_app" file_python.py
```

* Using a spec file:
```bash
pyinstaller name_app.spec
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

* Convert to ```.icns```:
```bash
iconutil -c icns my_icon.iconset
```
