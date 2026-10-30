"""Pos-processa o OMML do .docx: barras de modulo e funcao cos."""
import sys, zipfile, shutil, os
src = sys.argv[1]; tmp = src + ".tmp"
zin = zipfile.ZipFile(src)
zout = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = zin.read(item.filename)
    if item.filename == "word/document.xml":
        x = data.decode("utf8")
        n = x.count("§ABS§")
        x = x.replace('<m:d><m:dPr/><m:e><m:r><m:t>§ABS§</m:t></m:r>',
                      '<m:d><m:dPr><m:begChr m:val="|"/><m:endChr m:val="|"/></m:dPr><m:e>')
        x = x.replace('<m:r><m:t>§COS§</m:t></m:r>',
                      '<m:func><m:funcPr/><m:fName><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>cos</m:t></m:r></m:fName>'
                      '<m:e><m:r><m:t>θ</m:t></m:r></m:e></m:func>')
        assert "§" not in x, "marcador nao substituido"
        print("modulos:", n)
        data = x.encode("utf8")
    zout.writestr(item, data)
zout.close(); zin.close(); shutil.move(tmp, src)
