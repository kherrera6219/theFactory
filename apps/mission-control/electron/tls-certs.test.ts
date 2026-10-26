import crypto from "crypto";
import fs from "fs";
import os from "os";
import path from "path";
import tls from "tls";
import { afterEach, describe, expect, it } from "vitest";
import { ensureTlsCertificates } from "./tls-certs";

const dirs: string[] = [];

afterEach(() => {
  dirs.splice(0).forEach((d) => fs.rmSync(d, { recursive: true, force: true }));
});

describe("ensureTlsCertificates", () => {
  it("generates valid X.509 v3 CA + leaf bundles for Postgres and Redis using native crypto", () => {
    const certsRoot = fs.mkdtempSync(path.join(os.tmpdir(), "hgr-tls-"));
    dirs.push(certsRoot);

    ensureTlsCertificates(certsRoot);

    for (const [subDir, base, cn, caCn, dnsName] of [
      ["postgres-certs", "server", "postgres", "theFactory Postgres Dev CA", "postgres"],
      ["redis-certs", "redis", "redis", "theFactory Redis Dev CA", "redis"],
    ] as const) {
      const dir = path.join(certsRoot, subDir);
      const caPem = fs.readFileSync(path.join(dir, "ca.crt"), "utf-8");
      const leafPem = fs.readFileSync(path.join(dir, `${base}.crt`), "utf-8");
      const keyPem = fs.readFileSync(path.join(dir, `${base}.key`), "utf-8");

      const caCert = new crypto.X509Certificate(caPem);
      const leafCert = new crypto.X509Certificate(leafPem);

      expect(caCert.ca).toBe(true);
      expect(caCert.subject).toContain(`CN=${caCn}`);
      expect(caCert.verify(caCert.publicKey)).toBe(true);

      expect(leafCert.ca).toBe(false);
      expect(leafCert.subject).toContain(`CN=${cn}`);
      expect(leafCert.issuer).toContain(`CN=${caCn}`);
      expect(leafCert.subjectAltName).toContain(`DNS:${dnsName}`);
      expect(leafCert.subjectAltName).toContain("DNS:localhost");
      expect(leafCert.subjectAltName).toContain("IP Address:127.0.0.1");
      expect(leafCert.verify(caCert.publicKey)).toBe(true);
      expect(leafCert.checkPrivateKey(crypto.createPrivateKey(keyPem))).toBe(true);

      // Verify OpenSSL / Node TLS accepts the bundle as a server context
      const ctx = tls.createSecureContext({
        ca: caPem,
        cert: leafPem,
        key: keyPem,
      });
      expect(ctx).toBeDefined();
    }

    // Second invocation is idempotent and leaves existing files intact
    const pgCertPath = path.join(certsRoot, "postgres-certs", "server.crt");
    const before = fs.readFileSync(pgCertPath, "utf-8");
    ensureTlsCertificates(certsRoot);
    expect(fs.readFileSync(pgCertPath, "utf-8")).toBe(before);
  });
});
