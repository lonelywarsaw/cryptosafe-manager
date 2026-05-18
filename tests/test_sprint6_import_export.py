import json
import os
import tempfile
import unittest
from unittest import mock

from core.import_export.exporter import ExportOptions, VaultExporter
from core.import_export.formats.csv_format import csv_to_entries, entries_to_csv
from core.import_export.formats.json_format import build_encrypted_export, parse_encrypted_export
from core.import_export.importer import VaultImporter
from core.import_export.key_exchange import (
    add_contact,
    generate_rsa_keypair,
    list_contacts,
    public_key_fingerprint,
    wrap_key_for_public,
)
from core.import_export import qr_codec
from core.import_export.sharing_service import SharingService
from core.key_manager import set_encryption_key


SAMPLE = [
    {
        "id": 1,
        "title": "Site",
        "username": "user",
        "password": "Secret1!",
        "url": "https://example.com",
        "notes": "note",
        "category": "work",
    }
]


class TestSprint6ImportExport(unittest.TestCase):
    def setUp(self):
        set_encryption_key(b"k" * 32)

    def test_encrypted_json_roundtrip(self):
        pkg = build_encrypted_export(SAMPLE, "export-pass-123")
        entries = parse_encrypted_export(pkg, "export-pass-123")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Site")
        self.assertEqual(entries[0]["password"], "Secret1!")

    def test_csv_and_bitwarden_paths(self):
        csv_text = entries_to_csv(SAMPLE)
        back = csv_to_entries(csv_text)
        self.assertEqual(back[0]["username"], "user")

    def test_exporter_and_importer_dry_run(self):
        exporter = VaultExporter(lambda: SAMPLE)
        pkg = exporter.export_encrypted_json("exp-pass", options=ExportOptions(include_notes=False))
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pkg, f)
        created = []

        def create_entry(data):
            row = dict(data)
            row["id"] = len(created) + 1
            created.append(row)
            return row

        importer = VaultImporter(create_entry=create_entry, list_entries=lambda: [])
        result = importer.import_file(path, "dry_run", export_password="exp-pass")
        self.assertEqual(len(result.added), 1)
        os.unlink(path)

    def test_rsa_wrapped_export(self):
        priv, pub = generate_rsa_keypair()
        pkg = build_encrypted_export(SAMPLE, "", recipient_public_key_pem=pub)
        entries = parse_encrypted_export(pkg, "", private_key_pem=priv)
        self.assertEqual(entries[0]["title"], "Site")

    def test_share_password_and_public_key(self):
        svc = SharingService()
        pkg = svc.create_password_share(SAMPLE[0], "share123", expires_days=2)
        entry = svc.import_share(pkg, share_password="share123")
        self.assertEqual(entry["username"], "user")

        priv, pub = generate_rsa_keypair()
        pkg2 = svc.create_public_key_share(SAMPLE[0], pub, expires_days=3)
        entry2 = svc.import_share(pkg2, private_key_pem=priv)
        self.assertEqual(entry2["password"], "Secret1!")

    def test_qr_chunk_roundtrip(self):
        payload = qr_codec.build_payload("public_key", {"fingerprint": "abc", "pem": "test"})
        chunks = qr_codec.encode_chunks(payload)
        self.assertGreaterEqual(len(chunks), 1)
        with mock.patch.object(qr_codec, "MAX_CHUNK_LEN", 120):
            big = qr_codec.build_payload("share_package", {"blob_hint": "y" * 400})
            multi = qr_codec.encode_chunks(big)
        self.assertGreater(len(multi), 1)
        decoded = qr_codec.decode_chunks(multi)
        self.assertEqual(decoded["type"], "share_package")

    def test_contacts(self):
        _, pub = generate_rsa_keypair()
        fp = public_key_fingerprint(pub)
        add_contact("Alice", pub)
        contacts = [c for c in list_contacts() if c.get("fingerprint") == fp]
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["name"], "Alice")
