import ipaddress
import threading
from unittest.mock import patch

import pytest

from agent_browser import AgentBrowser,public_target


def test_preview_only_reads_existing_viewport():
    from unittest.mock import Mock
    browser = AgentBrowser()
    page = Mock()
    page.screenshot.return_value = b'png-viewport'
    browser.sessions['task'] = {'page': page, 'context': Mock()}
    try:
        assert browser.preview('task') == b'png-viewport'
        page.screenshot.assert_called_once_with(type='png', full_page=False, timeout=10000)
        page.goto.assert_not_called()
        with pytest.raises(ValueError, match='Open a browser page'):
            browser.preview('missing')
    finally:
        browser.close()


@pytest.mark.parametrize('url',['file:///C:/private','http://127.0.0.1','http://192.168.1.1','http://169.254.169.254','http://user:pass@example.test','https://example.test:8766'])
def test_browser_refuses_private_and_credentialed_urls(url):
    with pytest.raises(ValueError):public_target(url)


def test_dns_mixed_private_answer_is_blocked():
    with patch('agent_web._resolve',return_value=[ipaddress.ip_address('93.184.216.34'),ipaddress.ip_address('127.0.0.1')]),pytest.raises(ValueError):
        public_target('https://example.test')


def test_approved_click_cannot_be_retargeted_after_review():
    """The review fingerprint must include the effective navigation target, not just the label."""
    pytest.importorskip('playwright.sync_api')
    browser=AgentBrowser()
    page=b'<html><body><base href="https://example.test/"><a id="link" href="one">read</a></body></html>'
    try:
        with patch('agent_browser.public_target',return_value=(None,'93.184.216.34')),patch('agent_browser.fetch_request',return_value=(200,{'Content-Type':'text/html'},page)):
            opened=browser.execute('test','browser.open',{'url':'https://example.test'},{'url':'https://example.test'})
            click={'snapshot':opened['snapshot'],'element':0}
            binding=browser.prepare('test','browser.click',click)
            assert binding['target']['href'].endswith('/one')
            browser.executor.submit(lambda:browser._session('test')['page'].evaluate(
                "document.getElementById('link').setAttribute('href','https://collector.test/exfiltrate')")).result()
            with pytest.raises(ValueError,match='changed'):browser.execute('test','browser.click',click,binding)
    finally:browser.close()


def test_real_isolated_browser_interactions_and_stale_snapshot():
    pytest.importorskip('playwright.sync_api')
    browser=AgentBrowser()
    page=b'<html><body><p id="result">Browser test ready</p><input name="topic"><input type="password"><button onclick="document.getElementById(\'result\').textContent=\'Clicked safely\'">Run local demo</button></body></html>'
    try:
        with patch('agent_browser.public_target',return_value=(None,'93.184.216.34')),patch('agent_browser.fetch_request',return_value=(200,{'Content-Type':'text/html'},page)):
            opened=browser.execute('test','browser.open',{'url':'https://example.test'},{'url':'https://example.test'})
            assert 'Browser test ready' in opened['text']
            args={'snapshot':opened['snapshot'],'element':0,'text':'hello'}
            binding=browser.prepare('test','browser.fill',args)
            filled=browser.execute('test','browser.fill',args,binding)
            with pytest.raises(ValueError,match='snapshot'):browser.prepare('test','browser.fill',args)
            with pytest.raises(ValueError,match='Secret'):browser.prepare('test','browser.fill',{'snapshot':filled['snapshot'],'element':1})
            click={'snapshot':filled['snapshot'],'element':2}
            result=browser.execute('test','browser.click',click,browser.prepare('test','browser.click',click))
            assert 'Clicked safely' in result['text']
            assert browser.execute('test','browser.close',{},{} )['closed']
            with pytest.raises(ValueError):browser.prepare('test','browser.click',click)
    finally:browser.close()


def test_a_wedged_worker_is_retired_instead_of_blocking_approvals():
    """propose() waits on this thread while it holds the runtime lock, so it needs a deadline."""
    browser=AgentBrowser();browser.CALL_TIMEOUT=0.2
    stalled=threading.Event()
    browser.hang=lambda:stalled.wait(timeout=5)
    previous=browser.executor
    try:
        with pytest.raises(ValueError,match='stopped responding'):browser.call('hang')
        assert browser.executor is not previous,'the blocked worker stayed in service'
        # A second live driver could not be closed from here (Playwright is thread-affine), so
        # the tools retire instead of stacking another cookie-bearing browser per wedge.
        assert browser.browser is None and browser.driver is None
        with pytest.raises(ValueError,match='restart'):browser.prepare('task','browser.click',{'snapshot':'x','element':0})
        with pytest.raises(ValueError,match='restart'):browser.execute('task','browser.open',{'url':'https://example.test'},{})
        browser.cancel('task')
    finally:
        stalled.set()
        browser.close()


def test_failed_page_setup_does_not_leave_an_untracked_context():
    browser=AgentBrowser()
    class Context:
        def __init__(self):self.closed=False
        def route(self,*args,**kwargs):pass
        def route_web_socket(self,*args,**kwargs):pass
        def add_init_script(self,*args,**kwargs):raise RuntimeError('init script failed')
        def close(self):self.closed=True
    context=Context()
    browser.browser=type('Driver',(),{'new_context':lambda self,**kwargs:context})()
    try:
        with patch('agent_browser.public_target',return_value=(None,'93.184.216.34')):
            with pytest.raises(RuntimeError,match='init script failed'):
                browser.execute('task','browser.open',{'url':'https://example.test'},{'url':'https://example.test'})
        assert context.closed,'a cookie-bearing context outlived the task that failed to open it'
        assert not browser.sessions and not browser.events
    finally:
        browser.browser=None
        browser.close()


def test_timeout_closes_the_owned_process_job():
    from unittest.mock import Mock
    browser=AgentBrowser();browser.CALL_TIMEOUT=0.02
    released=threading.Event();owner=Mock()
    browser.process_owner=owner
    browser.hang=lambda:released.wait(2)
    try:
        with pytest.raises(ValueError,match='stopped responding'):browser.call('hang')
        owner.close.assert_called_once()
        assert browser.process_owner is None
    finally:
        released.set();browser.close()


def test_windows_timeout_terminates_the_real_playwright_driver():
    import ctypes
    import os
    from ctypes import wintypes
    if os.name!='nt':pytest.skip('Windows process ownership')
    pytest.importorskip('playwright.sync_api')
    browser=AgentBrowser();released=threading.Event();handle=None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    try:
        browser.call('_launch')
        pid=browser.executor.submit(lambda:browser.driver._impl_obj._connection._transport._proc.pid).result(5)
        handle=kernel.OpenProcess(0x00100000,False,pid)
        assert handle
        assert kernel.WaitForSingleObject(handle,0)==258
        browser.CALL_TIMEOUT=0.05;browser.hang=lambda:released.wait(3)
        with pytest.raises(ValueError,match='stopped responding'):browser.call('hang')
        assert kernel.WaitForSingleObject(handle,3000)==0,'owned Playwright driver survived timeout'
    finally:
        released.set();browser.close()
        if handle:kernel.CloseHandle(handle)
