import crypto from "crypto";
import fs from "fs";
import path from "path";

// Replicates scripts/generate_dev_tls_certs.sh using Node's native `crypto`
// module (no external JS ASN.1 library and no openssl CLI dependency) for the
// packaged Electron installer, which cannot assume an end-user's machine has
// OpenSSL on PATH. Produces the same file layout (ca.crt, <base>.crt,
// <base>.key) with matching CN/SAN/validity so the bundled Redis/Postgres
// images' TLS-only configs accept the connection.

const CERT_DAYS = 825;
const KEY_BITS = 2048;

export type CertBundle = {
  caCertPem: string;
  certPem: string;
  keyPem: string;
};

// Minimal ASN.1 DER encoding helpers for X.509 v3 certificate synthesis.
function derLength(length: number): Buffer {
  if (length < 0x80) {
    return Buffer.from([length]);
  }
  const bytes: number[] = [];
  let remaining = length;
  while (remaining > 0) {
    bytes.unshift(remaining & 0xff);
    remaining >>= 8;
  }
  return Buffer.from([0x80 | bytes.length, ...bytes]);
}

function derTlv(tag: number, content: Buffer): Buffer {
  return Buffer.concat([Buffer.from([tag]), derLength(content.length), content]);
}

function derSequence(items: Buffer[]): Buffer {
  return derTlv(0x30, Buffer.concat(items));
}

function derSet(items: Buffer[]): Buffer {
  return derTlv(0x31, Buffer.concat(items));
}

function derInteger(value: number): Buffer {
  return derTlv(0x02, Buffer.from([value & 0xff]));
}

function derBoolean(value: boolean): Buffer {
  return derTlv(0x01, Buffer.from([value ? 0xff : 0x00]));
}

function derOctetString(content: Buffer): Buffer {
  return derTlv(0x04, content);
}

function derBitString(content: Buffer, unusedBits = 0): Buffer {
  return derTlv(0x03, Buffer.concat([Buffer.from([unusedBits]), content]));
}

function derUtf8String(text: string): Buffer {
  return derTlv(0x0c, Buffer.from(text, "utf8"));
}

function derOid(oid: string): Buffer {
  const parts = oid.split(".").map((n) => parseInt(n, 10));
  const bytes: number[] = [40 * parts[0] + parts[1]];
  for (let i = 2; i < parts.length; i += 1) {
    let val = parts[i];
    const encoded: number[] = [val & 0x7f];
    val >>= 7;
    while (val > 0) {
      encoded.unshift((val & 0x7f) | 0x80);
      val >>= 7;
    }
    bytes.push(...encoded);
  }
  return derTlv(0x06, Buffer.from(bytes));
}

function derUtcOrGeneralizedTime(date: Date): Buffer {
  const year = date.getUTCFullYear();
  const pad2 = (n: number) => String(n).padStart(2, "0");
  const rest =
    pad2(date.getUTCMonth() + 1) +
    pad2(date.getUTCDate()) +
    pad2(date.getUTCHours()) +
    pad2(date.getUTCMinutes()) +
    pad2(date.getUTCSeconds()) +
    "Z";
  if (year >= 1950 && year <= 2049) {
    return derTlv(0x17, Buffer.from(pad2(year % 100) + rest, "ascii"));
  }
  return derTlv(0x18, Buffer.from(String(year) + rest, "ascii"));
}

function derCommonNameDistinguishedName(cn: string): Buffer {
  // Name ::= SEQUENCE { RelativeDistinguishedName ::= SET { AttributeTypeAndValue } }
  // OID 2.5.4.3 = id-at-commonName
  return derSequence([derSet([derSequence([derOid("2.5.4.3"), derUtf8String(cn)])])]);
}

function derExtension(oid: string, critical: boolean, extnValue: Buffer): Buffer {
  const items: Buffer[] = [derOid(oid)];
  if (critical) {
    items.push(derBoolean(true));
  }
  items.push(derOctetString(extnValue));
  return derSequence(items);
}

function derPemFromCertDer(certDer: Buffer): string {
  const b64 = certDer.toString("base64");
  const lines = b64.match(/.{1,64}/g) ?? [b64];
  return `-----BEGIN CERTIFICATE-----\n${lines.join("\n")}\n-----END CERTIFICATE-----\n`;
}

// SHA256withRSA AlgorithmIdentifier:SEQUENCE { OID 1.2.840.113549.1.1.11, NULL }
const SHA256_WITH_RSA_ALG_ID = derSequence([
  derOid("1.2.840.113549.1.1.11"),
  Buffer.from([0x05, 0x00]),
]);

function signX509Certificate(options: {
  serial: number;
  issuerCn: string;
  subjectCn: string;
  notBefore: Date;
  notAfter: Date;
  subjectPublicKey: crypto.KeyObject;
  issuerPrivateKey: crypto.KeyObject;
  extensions: Buffer[];
}): string {
  const versionExplicit = derTlv(0xa0, derInteger(2)); // v3 = 2
  const validity = derSequence([
    derUtcOrGeneralizedTime(options.notBefore),
    derUtcOrGeneralizedTime(options.notAfter),
  ]);
  const spkiDer = options.subjectPublicKey.export({
    type: "spki",
    format: "der",
  }) as Buffer;
  const extensionsExplicit = derTlv(0xa3, derSequence(options.extensions));

  const tbsCertificate = derSequence([
    versionExplicit,
    derInteger(options.serial),
    SHA256_WITH_RSA_ALG_ID,
    derCommonNameDistinguishedName(options.issuerCn),
    validity,
    derCommonNameDistinguishedName(options.subjectCn),
    spkiDer,
    extensionsExplicit,
  ]);

  const signature = crypto.sign("sha256", tbsCertificate, options.issuerPrivateKey);
  const certDer = derSequence([
    tbsCertificate,
    SHA256_WITH_RSA_ALG_ID,
    derBitString(signature, 0),
  ]);
  return derPemFromCertDer(certDer);
}

function buildSubjectAltNameExtension(
  sans: Array<{ type: "DNS" | "IP"; value: string }>,
): Buffer {
  const generalNames = sans.map((san) => {
    if (san.type === "DNS") {
      // dNSName [2] IA5String (context-specific primitive tag 0x82)
      return derTlv(0x82, Buffer.from(san.value, "ascii"));
    }
    // iPAddress [7] OCTET STRING (context-specific primitive tag 0x87)
    const octets = san.value.split(".").map((part) => parseInt(part, 10) & 0xff);
    return derTlv(0x87, Buffer.from(octets));
  });
  // OID 2.5.29.17 = id-ce-subjectAltName
  return derExtension("2.5.29.17", false, derSequence(generalNames));
}

function notAfter(days: number): Date {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date;
}

/** Generate a self-signed CA plus a leaf certificate signed by it, matching
 * generate_dev_tls_certs.sh's generate_bundle() (CN, CA name, SAN list). */
function generateBundle(options: {
  commonName: string;
  caName: string;
  sans: Array<{ type: "DNS" | "IP"; value: string }>;
}): CertBundle {
  const now = new Date();
  const validUntil = notAfter(CERT_DAYS);

  const caKeys = crypto.generateKeyPairSync("rsa", { modulusLength: KEY_BITS });
  const caExtensions = [
    // basicConstraints (2.5.29.19): BasicConstraints ::= SEQUENCE { cA BOOLEAN TRUE }
    derExtension("2.5.29.19", true, derSequence([derBoolean(true)])),
    // keyUsage (2.5.29.15): digitalSignature (bit 0), keyCertSign (bit 5), cRLSign (bit 6)
    // Bits: 10000110 = 0x86, unused bits = 1
    derExtension("2.5.29.15", true, derBitString(Buffer.from([0x86]), 1)),
  ];
  const caCertPem = signX509Certificate({
    serial: 1,
    issuerCn: options.caName,
    subjectCn: options.caName,
    notBefore: now,
    notAfter: validUntil,
    subjectPublicKey: caKeys.publicKey,
    issuerPrivateKey: caKeys.privateKey,
    extensions: caExtensions,
  });

  const leafKeys = crypto.generateKeyPairSync("rsa", { modulusLength: KEY_BITS });
  const leafExtensions = [
    // basicConstraints (2.5.29.19): BasicConstraints ::= SEQUENCE {} (cA DEFAULT FALSE)
    derExtension("2.5.29.19", true, derSequence([])),
    // keyUsage (2.5.29.15): digitalSignature (bit 0), keyEncipherment (bit 2)
    // Bits: 10100000 = 0xa0, unused bits = 5
    derExtension("2.5.29.15", true, derBitString(Buffer.from([0xa0]), 5)),
    // extKeyUsage (2.5.29.37): id-kp-serverAuth (1.3.6.1.5.5.7.3.1)
    derExtension("2.5.29.37", false, derSequence([derOid("1.3.6.1.5.5.7.3.1")])),
    buildSubjectAltNameExtension(options.sans),
  ];
  const certPem = signX509Certificate({
    serial: 2,
    issuerCn: options.caName,
    subjectCn: options.commonName,
    notBefore: now,
    notAfter: validUntil,
    subjectPublicKey: leafKeys.publicKey,
    issuerPrivateKey: caKeys.privateKey,
    extensions: leafExtensions,
  });

  const keyPem = leafKeys.privateKey.export({
    type: "pkcs1",
    format: "pem",
  }) as string;

  return {
    caCertPem,
    certPem,
    keyPem,
  };
}

function writeBundle(dir: string, base: string, bundle: CertBundle): void {
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "ca.crt"), bundle.caCertPem, { mode: 0o644 });
  fs.writeFileSync(path.join(dir, `${base}.crt`), bundle.certPem, { mode: 0o644 });
  fs.writeFileSync(path.join(dir, `${base}.key`), bundle.keyPem, { mode: 0o600 });
}

function bundleExists(dir: string, base: string): boolean {
  return (
    fs.existsSync(path.join(dir, "ca.crt")) &&
    fs.existsSync(path.join(dir, `${base}.crt`)) &&
    fs.existsSync(path.join(dir, `${base}.key`))
  );
}

/** Generate the Postgres + Redis TLS bundles under certsRoot if they don't
 * already exist. Mirrors generate_dev_tls_certs.sh's postgres-certs/
 * redis-certs layout so the bundled compose volume mounts resolve the same
 * way regardless of whether certs came from the shell script (dev) or here
 * (packaged installer). */
export function ensureTlsCertificates(certsRoot: string): void {
  const postgresDir = path.join(certsRoot, "postgres-certs");
  const redisDir = path.join(certsRoot, "redis-certs");

  if (!bundleExists(postgresDir, "server")) {
    const bundle = generateBundle({
      commonName: "postgres",
      caName: "theFactory Postgres Dev CA",
      sans: [
        { type: "DNS", value: "postgres" },
        { type: "DNS", value: "localhost" },
        { type: "IP", value: "127.0.0.1" },
      ],
    });
    writeBundle(postgresDir, "server", bundle);
  }

  if (!bundleExists(redisDir, "redis")) {
    const bundle = generateBundle({
      commonName: "redis",
      caName: "theFactory Redis Dev CA",
      sans: [
        { type: "DNS", value: "redis" },
        { type: "DNS", value: "localhost" },
        { type: "IP", value: "127.0.0.1" },
      ],
    });
    writeBundle(redisDir, "redis", bundle);
  }
}
