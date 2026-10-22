import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock,patch

from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject,DictionaryObject,NameObject
from chat_attachments import AttachmentStore,extract_attachment
from llm import LLM


class AttachmentTests(unittest.TestCase):
    def test_text_docx_and_pdf_extract_real_contents(self):
        self.assertEqual(extract_attachment('notes.txt',b'Interview at 3 PM.')['text'],'Interview at 3 PM.')
        doc=io.BytesIO()
        with zipfile.ZipFile(doc,'w') as archive:
            archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Electrical engineering CV</w:t></w:r></w:p></w:body></w:document>')
        self.assertIn('Electrical engineering CV',extract_attachment('cv.docx',doc.getvalue())['text'])
        writer=PdfWriter();page=writer.add_blank_page(width=400,height=400)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 350 Td (Engineering projects and experience.) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(stream)
        pdf=io.BytesIO();writer.write(pdf)
        self.assertIn('Engineering projects',extract_attachment('resume.pdf',pdf.getvalue())['text'])

    def test_image_is_decoded_and_normalized(self):
        image=io.BytesIO();Image.new('RGBA',(60,40),(255,0,0,128)).save(image,'PNG')
        item=extract_attachment('photo.png',image.getvalue())
        self.assertEqual(item['kind'],'image')
        with Image.open(io.BytesIO(base64.b64decode(item['image']))) as read:self.assertEqual(read.format,'JPEG')

    def test_rejects_unsupported_binary_oversize_and_scanned_pdf(self):
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);blank=io.BytesIO();writer.write(blank)
        for name,data in [('app.exe',b'code'),('file.txt',b'\0binary'),('bad.png',b'not an image'),('scan.pdf',blank.getvalue()),('huge.txt',b'x'*(10*1024*1024+1))]:
            with self.assertRaises(ValueError,msg=name):extract_attachment(name,data)

    def test_tokens_expire_and_clear(self):
        store=AttachmentStore()
        with patch('chat_attachments.time.monotonic',return_value=100):item=store.put(extract_attachment('a.txt',b'hello'))
        with patch('chat_attachments.time.monotonic',return_value=200):self.assertEqual(store.get([item['id']])[0]['text'],'hello')
        with patch('chat_attachments.time.monotonic',return_value=4000),self.assertRaises(ValueError):store.get([item['id']])
        store.clear();self.assertEqual(store.items,{})

    def test_file_context_is_bounded_untrusted_and_not_fact_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');item=extract_attachment('a.txt',b'Projects. '*2000)
            with patch.object(model,'_request',return_value='This excerpt lists engineering projects.') as generate,patch('response_evidence.retrieve') as retrieve:
                self.assertEqual(model.chat('Summarize this',attachments=[item]),'This excerpt lists engineering projects.')
            retrieve.assert_not_called()
            messages=generate.call_args.args[0]
            self.assertIn('excerpt_only": true',messages[-1]['content'])
            self.assertIn('never instructions',' '.join(m['content'] for m in messages if m['role']=='system'))
            self.assertLess(len(messages[-1]['content']),5000)
            self.assertEqual(model.trusted_memory,[])
            self.assertNotIn('Projects.',str(model.history))

    def test_uploaded_image_uses_vision_and_is_not_called_live_camera(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            picture=io.BytesIO();Image.new('RGB',(32,32),'red').save(picture,'PNG')
            item=extract_attachment('square.png',picture.getvalue())
            with patch.object(model,'_request',return_value='This image shows a red square.') as generate:
                reply=model.chat('Describe this image',attachments=[item])
            self.assertIn('red square',reply)
            self.assertEqual(generate.call_args.kwargs['model'],model.vision_model)
            self.assertTrue(generate.call_args.args[0][-1]['images'])
            self.assertIn('not a live screen or camera',str(generate.call_args.args[0]))


class AttachmentEndpointTests(unittest.TestCase):
    def test_upload_and_chat_reach_selected_model_without_commands(self):
        import app as server
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'response_restriction_level':'off'}),patch.object(server.app.state,'tracking_only',False,create=True),patch.object(model,'_request',return_value='This CV describes electrical engineering projects.') as generate,patch('assistant_commands.run_command') as command:
                client=TestClient(server.app)
                upload=client.post('/api/chat/attachments',files={'file':('cv.txt',b'Electrical engineering projects and education.','text/plain')})
                self.assertEqual(upload.status_code,200)
                response=client.post('/api/chat',json={'text':'What is this?','attachments':[upload.json()['id']],'defer_audio':True})
                self.assertEqual(response.status_code,200)
                self.assertIn('electrical engineering',response.json()['reply'])
                self.assertIn('Electrical engineering projects',generate.call_args.args[0][-1]['content'])
                command.assert_not_called()
                self.assertEqual(client.delete('/api/chat/attachments/'+upload.json()['id']).status_code,200)
                self.assertEqual(client.post('/api/chat',json={'text':'summary','attachments':[upload.json()['id']]}).status_code,400)


if __name__=='__main__':unittest.main()
