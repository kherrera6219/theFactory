import fs from "fs";
import path from "path";
import forge from "node-forge";

// Replicates scripts/generate_dev_tls_certs.sh in pure JS (no openssl CLI
// dependency) for the packaged Electron installer, which cannot assume an
// end-user's machine has OpenSSL on PATH. Produces the same file layout
// (ca.crt, <base>.crt, <base>.key) with matching CN/SAN/validity so the
// bundled Redis/Postgres images' TLS-only configs accept the connection.

const CERT_DAYS = 825;
const KEY_BITS = 2048;

export type CertBundle = {
  caCertPem: string;
  certPem: string;
  keyPem: string;
};

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
  const caKeys = forge.pki.rsa.generateKeyPair(KEY_BITS);
  const caCert = forge.pki.createCertificate();
  caCert.publicKey = caKeys.publicKey;
  caCert.serialNumber = "01";
  caCert.validity.notBefore = new Date();
  caCert.validity.notAfter = notAfter(CERT_DAYS);
  const caAttrs = [{ name: "commonName", value: options.caName }];
  caCert.setSubject(caAttrs);
  caCert.setIssuer(caAttrs);
  caCert.setExtensions([
    { name: "basicConstraints", cA: true },
    { name: "keyUsage", keyCertSign: true, cRLSign: true, digitalSignature: true },
  ]);
  caCert.sign(caKeys.privateKey, forge.md.sha256.create());

  const leafKeys = forge.pki.rsa.generateKeyPair(KEY_BITS);
  const leafCert = forge.pki.createCertificate();
  leafCert.publicKey = leafKeys.publicKey;
  leafCert.serialNumber = "02";
  leafCert.validity.notBefore = new Date();
  leafCert.validity.notAfter = notAfter(CERT_DAYS);
  leafCert.setSubject([{ name: "commonName", value: options.commonName }]);
  leafCert.setIssuer(caAttrs);
  leafCert.setExtensions([
    { name: "basicConstraints", cA: false },
    { name: "keyUsage", digitalSignature: true, keyEncipherment: true },
    { name: "extKeyUsage", serverAuth: true },
    {
      name: "subjectAltName",
      altNames: options.sans.map((san) =>
        san.type === "DNS" ? { type: 2, value: san.value } : { type: 7, ip: san.value },
      ),
    },
  ]);
  leafCert.sign(caKeys.privateKey, forge.md.sha256.create());

  return {
    caCertPem: forge.pki.certificateToPem(caCert),
    certPem: forge.pki.certificateToPem(leafCert),
    keyPem: forge.pki.privateKeyToPem(leafKeys.privateKey),
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
