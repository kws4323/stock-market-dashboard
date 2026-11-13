import urllib.request, zipfile, io, xml.etree.ElementTree as E
url='https://www.gpif.go.jp/en/performance/73509681gpif/unyoujoukyou_2025_20_en_2.xlsx'
with urllib.request.urlopen(url,timeout=30) as r:z=zipfile.ZipFile(io.BytesIO(r.read()))
ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
strings=[''.join(t.itertext()) for t in E.fromstring(z.read('xl/sharedStrings.xml'))]
print(z.read('xl/workbook.xml').decode()[:5000])
for f in z.namelist():
 if f.startswith('xl/worksheets/sheet') and f.endswith('.xml'):
  print(f)
  for row in E.fromstring(z.read(f)).findall('.//x:row',ns)[:12]:
   out=[]
   for c in row:
    v=c.find('x:v',ns)
    if v is not None:out.append((c.get('r'),strings[int(v.text)] if c.get('t')=='s' else v.text))
   print(out)
