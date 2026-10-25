"""Self-signed TLS identity for the phone link.

The certificate is pinned by Sakura Mobile, so it is generated once beside the
paired-device store and never rotated implicitly: a new certificate would make
every paired phone reject the PC until it pairs again.
"""
import datetime
import hashlib
import ipaddress
import os
from pathlib import Path

CERT_NAME='phone-link.crt'
KEY_NAME='phone-link.key'
VALID_DAYS=3650


def fingerprint(certificate):
    from cryptography.hazmat.primitives import serialization
    return hashlib.sha256(certificate.public_bytes(serialization.Encoding.DER)).hexdigest()


def _atomic_write(path,data,private=False):
    pending=path.with_name(path.name+'.tmp')
    if private:
        descriptor=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(data)
    else:pending.write_bytes(data)
    pending.replace(path)


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
