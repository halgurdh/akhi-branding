#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Signs the unsigned .mar of a build on GitHub (make_update.py --unsigned) and writes its update-<target>.xml, as
signmar and make_update.py do on the PC, with mardor (pip install mar), the library Mozilla signs its updates with:

    AKHI_UPDATE_KEY_P12=<base64 of the .p12> AKHI_UPDATE_KEY_P12_PASSWORD=... \\
        python sign_mar.py <folder with the .mar.unsigned and update-info.json> [--base-url URL]

The .p12 is the key exported once from the NSS database with pk12util. The signature is checked with
update/primary.der, the certificate the browser trusts, and every file in the .mar must stay byte for byte the same.
"""

import argparse
import base64
import io
import json
import os
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from mardor.reader import MarReader
from mardor.writer import MarWriter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_update import update_xml  # noqa: E402

CERTIFICATE = Path(__file__).resolve().parents[1] / "update/primary.der"


def public_pem(public_key):
    return public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--base-url", help="Where the .mar will be, instead of the GitHub release (for a test)")
    parser.add_argument("--certificate", type=Path, default=CERTIFICATE, help="Instead of update/primary.der (a test)")
    args = parser.parse_args()

    info = json.loads((args.folder / "update-info.json").read_text(encoding="utf-8"))
    unsigned = args.folder / f"{info['name']}.unsigned"
    signed = args.folder / info["name"]

    key, certificate, _ = pkcs12.load_key_and_certificates(
        base64.b64decode(os.environ["AKHI_UPDATE_KEY_P12"]),
        os.environ["AKHI_UPDATE_KEY_P12_PASSWORD"].encode(),
    )
    trusted = public_pem(x509.load_der_x509_certificate(args.certificate.read_bytes()).public_key())
    if public_pem(key.public_key()) != trusted:
        sys.exit("The key of AKHI_UPDATE_KEY_P12 isn't the one of update/primary.der: the browser would refuse it")
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )

    with unsigned.open("rb") as source:
        reader = MarReader(source)
        if not reader.productinfo:
            sys.exit(f"{unsigned} has no product information (version and channel)")
        productversion, channel = reader.productinfo
        entries = []
        for entry in reader.mardata.index.entries:
            source.seek(entry.offset)
            entries.append((entry.name, entry.flags, source.read(entry.size)))

    with signed.open("w+b") as target:
        with MarWriter(
            target,
            productversion=productversion,
            channel=channel,
            signing_key=private,
            signing_algorithm="sha384",
        ) as writer:
            for name, flags, data in entries:
                writer.add_fileobj(io.BytesIO(data), name, compress=None, flags=flags)

    with signed.open("rb") as check:
        reader = MarReader(check)
        if not reader.verify(trusted):
            sys.exit(f"{signed}: the signature doesn't verify with update/primary.der")
        if reader.productinfo != (productversion, channel):
            sys.exit(f"{signed}: product information changed")
        again = []
        for entry in reader.mardata.index.entries:
            check.seek(entry.offset)
            again.append((entry.name, entry.flags, check.read(entry.size)))
        if again != entries:
            sys.exit(f"{signed}: its files differ from the unsigned .mar")

    data = signed.read_bytes()
    xml = update_xml(
        info["version"], info["app_version"], info["platform_version"], info["build_id"], info["name"], data,
        args.base_url,
    )
    (args.folder / f"update-{info['target']}.xml").write_text(xml, encoding="utf-8")
    unsigned.unlink()
    print(f"signed {signed.name} ({len(entries)} files, {productversion}, {channel}), checked with primary.der")


if __name__ == "__main__":
    main()
