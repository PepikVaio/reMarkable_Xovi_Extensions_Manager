
## Create app from python:
pyinstaller --onefile --windowed --name "name_app" file_python.py

## Create app from python with terminal:
pyinstaller --onefile --name "name_app" file_python.py


## Run with spec file:
pyinstaller name_app.spec



Image icns from png: (text to terminal)

mkdir my_icon.iconset
sips -z 16 16     myimage.png --out MyIcon.iconset/icon_16x16.png
sips -z 32 32     myimage.png --out MyIcon.iconset/icon_16x16@2x.png
sips -z 32 32     myimage.png --out MyIcon.iconset/icon_32x32.png
sips -z 64 64     myimage.png --out MyIcon.iconset/icon_32x32@2x.png
sips -z 128 128   myimage.png --out MyIcon.iconset/icon_128x128.png
sips -z 256 256   myimage.png --out MyIcon.iconset/icon_128x128@2x.png
sips -z 256 256   myimage.png --out MyIcon.iconset/icon_256x256.png
sips -z 512 512   myimage.png --out MyIcon.iconset/icon_256x256@2x.png
sips -z 512 512   myimage.png --out MyIcon.iconset/icon_512x512.png
sips -z 1024 1024 myimage.png --out MyIcon.iconset/icon_512x512@2x.png

Then text to terminal:
iconutil -c icns MyIcon.iconset

