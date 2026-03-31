pip install -r requirements.txt
pyinstaller --onefile --windowed main.py -n "OCLC retained holdings" --distpath "%cd%" --workpath exe_build --noconfirm
del "OCLC retained holdings.spec"
rmdir /Q /S exe_build
pause
