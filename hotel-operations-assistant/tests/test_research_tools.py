import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import hashlib
import json

spec=importlib.util.spec_from_file_location('research',Path(__file__).resolve().parents[1]/'scripts'/'research_tools.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
S=mod.NS['s'];R=mod.NS['r']

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def xlsx(self,price='300',formula='',images=False):
        p=self.root/'sample.xlsx'
        with ZipFile(p,'w') as z:
            z.writestr('xl/workbook.xml',f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Sheet1" sheetId="1" r:id="r1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            cells=f'<c r="A3"><v>46273</v></c><c r="B3">{formula}<v>{price}</v></c>'
            if images:cells+='<c r="C3"><f>_xlfn.DISPIMG("ID_TEST",1)</f></c><c r="D3"><f>_xlfn.DISPIMG("ID_TEST",1)</f></c>'
            z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{S}"><sheetData><row r="3">{cells}</row></sheetData></worksheet>')
            if images:
                z.writestr('xl/cellimages.xml',f'<cellImages xmlns:xdr="{mod.NS["xdr"]}" xmlns:a="{mod.NS["a"]}" xmlns:r="{R}"><cellImage><xdr:pic><xdr:cNvPr name="ID_TEST"/><a:blip r:embed="p1"/></xdr:pic></cellImage></cellImages>')
                z.writestr('xl/_rels/cellimages.xml.rels','<Relationships><Relationship Id="p1" Target="media/image1.png"/></Relationships>')
                z.writestr('xl/media/','');z.writestr('xl/media/image1.png',b'fictional-image-bytes')
        return p

    def config(self):return dict(sheet='Sheet1',date_column='A',date_mode='excel',start_row=3,end_row=3,groups=[dict(hotel='Fictional',observations=[dict(column='B',time='16:00')])])
    def output(self):p=self.root/'out';p.mkdir();return p

    def test_prices_source_tracking(self):
        source=self.xlsx();before=source.read_bytes();out=self.output();r=mod.export_prices(source,self.config(),out)
        self.assertEqual(r['summary'][0]['mean'],'300.0000');self.assertEqual(r['valid_points'],1)
        self.assertIn('B3',(out/'observations.csv').read_text(encoding='utf-8-sig'));self.assertEqual(source.read_bytes(),before)

    def test_missing_price_not_zero(self):
        r=mod.export_prices(self.xlsx(price=''),self.config(),self.output());self.assertEqual(r['valid_points'],0);self.assertTrue(r['statistics_provisional'])

    def test_formula_not_cached_result(self):
        r=mod.export_prices(self.xlsx(formula='<f>100+200</f>'),self.config(),self.output());self.assertEqual(r['valid_points'],0)

    def test_zero_price_requires_review(self):
        r=mod.export_prices(self.xlsx(price='0'),self.config(),self.output());self.assertEqual(r['issues'][0]['issue'],'INVALID_PRICE')

    def test_duplicate_column_rejected(self):
        c=self.config();c['groups'].append(c['groups'][0])
        with self.assertRaises(ValueError):mod.export_prices(self.xlsx(),c,self.output())

    def test_excel_date_systems(self):
        self.assertEqual(mod.observation_date('0','excel',True),'1904-01-01')
        self.assertEqual(mod.observation_date('1','excel',False),'1900-01-01')
        self.assertEqual(mod.observation_date('46273','excel',False),'2026-09-08')
        with self.assertRaises(ValueError):mod.observation_date('60','excel',False)

    def test_relationship_escape_rejected(self):
        with self.assertRaises(ValueError):mod.target_path('xl/workbook.xml','../../outside')
        self.assertEqual(mod.target_path('xl/worksheets/sheet1.xml','../drawings/drawing1.xml'),'xl/drawings/drawing1.xml')

    def test_image_mapping_dedup_and_directory_excluded(self):
        source=self.xlsx(images=True);before=source.read_bytes();r=mod.image_index(source,self.output())
        self.assertEqual(r['media_members'],1);self.assertEqual(r['placements'],2);self.assertEqual(r['unique_exported_images'],1)
        self.assertEqual([x['cell'] for x in r['items']],['C3','D3']);self.assertEqual(source.read_bytes(),before)

    def test_documents_preserve_locations(self):
        source=self.root/'a.md';source.write_text('标题\n\n示例假设180间\n',encoding='utf-8')
        # Write real line breaks for location checks.
        source.write_text('标题'+chr(10)+chr(10)+'示例假设180间'+chr(10),encoding='utf-8')
        r=mod.document_passages([source],self.output());self.assertEqual(r['documents'][0]['passages'][1]['position'],3)

    def test_docx_table_paragraphs(self):
        source=self.root/'a.docx'
        with ZipFile(source,'w') as z:z.writestr('word/document.xml',f'<w:document xmlns:w="{mod.NS["w"]}"><w:body><w:p><w:r><w:t>假设</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>180</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        r=mod.document_passages([source],self.output());self.assertEqual([x['text'] for x in r['documents'][0]['passages']],['假设','180'])

if __name__=='__main__':unittest.main()
