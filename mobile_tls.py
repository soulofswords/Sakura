"""Self-signed TLS identity for the phone link.

The certificate is pinned by Sakura Mobile, so it is generated once beside the
paired-device store and never rotated implicitly: a new certificate would make
every paired phone reject the PC until it pairs again.
"""
import datetime
import hashlib
import ipaddress
import os
import tempfile
from functools import lru_cache
from pathlib import Path

CERT_NAME='phone-link.crt'
KEY_NAME='phone-link.key'
VALID_DAYS=3650


def fingerprint(certificate):
    from cryptography.hazmat.primitives import serialization
    return hashlib.sha256(certificate.public_bytes(serialization.Encoding.DER)).hexdigest()


@lru_cache(maxsize=1)
def _windows_owner_sid():
    import csv
    import re
    import subprocess
    system=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'
    result=subprocess.run([str(system/'whoami.exe'),'/user','/fo','csv','/nh'],
        capture_output=True,text=True,check=True,timeout=10,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    rows=list(csv.reader(result.stdout.strip().splitlines()))
    sid=rows[0][-1] if len(rows)==1 and rows[0] else ''
    if not re.fullmatch(r'S-1-\d+(?:-\d+)+',sid):
        raise OSError('Could not identify the owner of the phone-link key.')
    return sid


def restrict_private_key(path):
    """Protect new and existing keys without rotating the pinned identity."""
    if os.name!='nt':
        os.chmod(path,0o600)
        return
    import ctypes
    from ctypes import wintypes
    sid=_windows_owner_sid()
    advapi=ctypes.WinDLL('advapi32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    convert=advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.ULONG)]
    convert.restype=wintypes.BOOL
    protect=advapi.SetFileSecurityW
    protect.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,ctypes.c_void_p]
    protect.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    descriptor=ctypes.c_void_p()
    # Protected DACL: no inherited Users/Authenticated Users permissions.
    inherit='OICI' if Path(path).is_dir() else ''
    sddl=f'D:P(A;{inherit};FA;;;SY)(A;{inherit};FA;;;BA)(A;{inherit};FA;;;{sid})'
    if not convert(sddl,1,ctypes.byref(descriptor),None):raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not protect(str(Path(path).resolve()),0x80000004,descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:kernel.LocalFree(descriptor)


def _atomic_write(path,data,private=False):
    descriptor,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    pending=Path(name)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            if private:restrict_private_key(pending)
            stream.write(data)
        pending.replace(path)
    finally:pending.unlink(missing_ok=True)


def _existing(cert_path,key_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    try:
        certificate=x509.load_pem_x509_certificate(cert_path.read_bytes())
        key=serialization.load_pem_private_key(key_path.read_bytes(),password=None)
    except (OSError,ValueError):return None
    if not isinstance(key,ec.EllipticCurvePrivateKey):return None
    if key.public_key().public_numbers()!=certificate.public_key().public_numbers():return None
    expires=getattr(certificate,'not_valid_after_utc',None)
    if expires is not None and expires<=datetime.datetime.now(datetime.timezone.utc):return None
    return {'cert':str(cert_path),'key':str(key_path),'fingerprint':fingerprint(certificate)}


def ensure_identity(directory):
    directory=Path(directory);cert_path=directory/CERT_NAME;key_path=directory/KEY_NAME
    if key_path.exists():restrict_private_key(key_path)
    existing=_existing(cert_path,key_path)
    if existing:return existing
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
    directory.mkdir(parents=True,exist_ok=True)
    key=ec.generate_private_key(ec.SECP256R1())
    now=datetime.datetime.now(datetime.timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Sakura Phone Link')])
    certificate=(x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
            x509.IPAddress(ipaddress.ip_address('127.0.0.1')),x509.IPAddress(ipaddress.ip_address('::1'))]),critical=False)
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
        .sign(key,hashes.SHA256()))
    _atomic_write(key_path,key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,serialization.NoEncryption()),private=True)
    _atomic_write(cert_path,certificate.public_bytes(serialization.Encoding.PEM))
    return {'cert':str(cert_path),'key':str(key_path),'fingerprint':fingerprint(certificate)}
