"""Native Apple Silicon startup chooser; AI dependencies remain optional."""
import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QProcess
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QComboBox, QProgressBar)
from local_model_setup import installed

BASE = Path(__file__).resolve().parent
STYLE = '''QWidget{background:#0c0f1a;color:#f0f4ff;font:15px;} QPushButton,
QLineEdit,QComboBox{background:#171e2e;border:1px solid #394764;padding:12px;border-radius:8px;}
QPushButton:hover{border-color:#61e1eb;} QLabel{padding:8px;}'''

class Download(QDialog):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Sakura — Optional local AI')
        self.setMinimumWidth(560); self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Choose your local companion'))
        self.choice = QComboBox(); self.choice.addItems(['Qwen 2B', 'Qwen 4B'])
        layout.addWidget(self.choice)
        guidance = QLabel('2B: 8 GB unified memory minimum; 16 GB preferred.\n4B: 16 GB unified memory recommended.\nM1 or newer, macOS 14+. Allow 8–10 GB free disk.\nThese are recommendations; other apps share your memory.')
        guidance.setWordWrap(True); layout.addWidget(guidance)
        self.status = QLabel('No downloads until you press Download.'); self.status.setWordWrap(True);layout.addWidget(self.status)
        self.bar = QProgressBar();self.bar.setRange(0,0);self.bar.hide();layout.addWidget(self.bar)
        self.button = QPushButton('Download and use local AI');layout.addWidget(self.button)
        self.button.clicked.connect(self.start)
        self.worker = QProcess(self);self.worker.setWorkingDirectory(str(BASE))
        self.pending = ''
        self.worker.setProcessChannelMode(QProcess.MergedChannels)
        self.worker.readyReadStandardOutput.connect(self.output)
        self.worker.finished.connect(self.finished)
        self.worker.errorOccurred.connect(lambda _: self.failed('Could not start the downloader.'))
        cancel = QPushButton('Cancel');cancel.clicked.connect(self.reject);layout.addWidget(cancel)
    def start(self):
        self.button.setEnabled(False);self.choice.setEnabled(False);self.bar.show()
        self.worker.start(sys.executable, ['-u', str(BASE/'local_model_setup.py'), '--install', '2b' if self.choice.currentIndex()==0 else '4b'])
    def output(self):
        import json
        self.pending += bytes(self.worker.readAllStandardOutput()).decode('utf-8',errors='replace')
        lines = self.pending.split('\n'); self.pending = lines.pop()
        for line in lines:
            try:self.status.setText(json.loads(line)['message'])
            except (ValueError,KeyError):self.status.setText(line)
    def failed(self,message):
        self.status.setText(message);self.bar.hide();self.button.setEnabled(True);self.choice.setEnabled(True)
    def finished(self,code,_):
        if code==0:self.accept()
        else:self.failed('Download failed. Retry to resume. '+self.status.text())
    def reject(self):
        if self.worker.state()!=QProcess.NotRunning:
            self.worker.terminate()
            if not self.worker.waitForFinished(5000):self.worker.kill();self.worker.waitForFinished(3000)
        super().reject()

class Chooser(QDialog):
    mode = None
    def __init__(self):
        super().__init__();self.setWindowTitle('Sakura Companion');self.setMinimumWidth(540)
        self.setStyleSheet(STYLE);self.setWindowIcon(QIcon(str(BASE/'launcher/companion.ico')))
        layout=QVBoxLayout(self);layout.addWidget(QLabel('Welcome to Sakura\nChoose your experience'))
        self.provider=QComboBox();self.providers=['auto','gemini','openai','anthropic','deepseek','openrouter','groq','xai']
        self.provider.addItems(['Auto-detect API key','Google Gemini','OpenAI','Anthropic Claude','DeepSeek','OpenRouter','Groq','xAI']);layout.addWidget(self.provider)
        self.key=QLineEdit();self.key.setEchoMode(QLineEdit.Password);self.key.setPlaceholderText('Cloud API key — leave blank to use saved provider/key');layout.addWidget(self.key)
        self.model=QLineEdit();self.model.setPlaceholderText('Model ID (required for OpenRouter/Groq/xAI)');layout.addWidget(self.model)
        for mode,label in [('gemini','Cloud API — cloud companion'),('local','Local LLM — on this Mac'),('vtuber','VTuber — face and hand tracking, no AI')]:
            button=QPushButton(label);button.clicked.connect(lambda _,m=mode:self.choose(m));layout.addWidget(button)
        feedback=QLabel('This app is currently under development. Your feedback is most important.<br>'
            '<a href="https://discord.gg/kgxeMRFWDw">Join my Discord and DM me</a>')
        feedback.setWordWrap(True);feedback.setOpenExternalLinks(True);layout.addWidget(feedback)
    def choose(self,mode):
        if mode=='gemini' and not self.key.text().strip():
            from credentials import get_gemini_key,get_cloud_key
            import json
            try:cfg=json.loads((BASE/'settings.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):cfg={}
            provider=cfg.get('llm_provider','gemini')
            if provider=='ollama':provider=cfg.get('last_cloud_provider','gemini')
            try:saved=get_gemini_key() if provider=='gemini' else get_cloud_key(provider,cfg.get('cloud_endpoint',''))
            except OSError:saved=''
            if not saved:QMessageBox.information(self,'API key','Enter an API key to continue.');return
        if mode=='gemini' and self.key.text().strip():
            from cloud_api import detect_provider
            try:provider=detect_provider(self.key.text().strip()) if self.provider.currentIndex()==0 else self.providers[self.provider.currentIndex()]
            except ValueError as error:QMessageBox.information(self,'Choose provider',str(error));return
            if provider in ('openrouter','groq','xai') and not self.model.text().strip():
                QMessageBox.information(self,'Model ID','Enter the model ID from your provider.');return
            os.environ['SAKURA_START_API_PROVIDER']=provider
            os.environ['SAKURA_START_CLOUD_MODEL']=self.model.text().strip()
        if mode=='local' and not installed():
            if QMessageBox.question(self,'Set up local AI','Are you sure you want to run Local LLM? A runtime and your selected Qwen model will be downloaded.')!=QMessageBox.Yes:return
            if Download().exec()!=QDialog.Accepted:return
        self.mode=mode;self.accept()

if __name__=='__main__':
    application=QApplication(sys.argv)
    if '--setup-local' in sys.argv:
        sys.exit(0 if Download().exec()==QDialog.Accepted else 1)
    dialog=Chooser()
    if dialog.exec()!=QDialog.Accepted:sys.exit(0)
    os.environ['SAKURA_START_MODE']=dialog.mode
    if dialog.mode=='gemini' and dialog.key.text().strip():os.environ['SAKURA_START_GEMINI_KEY']=dialog.key.text().strip()
    os.execv(sys.executable,[sys.executable,str(BASE/'desktop.py')])
