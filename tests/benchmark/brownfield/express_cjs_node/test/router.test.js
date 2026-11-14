'use strict';

const assert = require('assert');
const { InventoryStore, createInventoryRouter } = require('../src/router');

function invokeRoute(router, method, path, reqOverrides) {
  const route = router._routes.find((r) => r.method === method && r.path === path);
  assert.ok(route, `Route ${method} ${path} should be registered`);
  let capturedStatus = 200;
  let capturedBody = null;
  const res = {
    status(code) {
      capturedStatus = code;
      return res;
    },
    json(payload) {
      capturedBody = payload;
      return { status: capturedStatus, body: capturedBody };
    },
  };
  route.handler(Object.assign({ params: {}, body: {}, query: {} }, reqOverrides), res);
  return { status: capturedStatus, body: capturedBody };
}

(function runTests() {
  const store = new InventoryStore();
  const router = createInventoryRouter(store, null);

  const created = invokeRoute(router, 'POST', '/inventory', {
    body: { sku: 'SKU-100', qty: 5 },
  });
  assert.strictEqual(created.status, 201);
  assert.deepStrictEqual(created.body, { sku: 'SKU-100', qty: 5 });

  const listed = invokeRoute(router, 'GET', '/inventory', {});
  assert.strictEqual(listed.status, 200);
  assert.strictEqual(listed.body.total, 1);

  const fetched = invokeRoute(router, 'GET', '/inventory/:sku', {
    params: { sku: 'SKU-100' },
  });
  assert.strictEqual(fetched.status, 200);
  assert.strictEqual(fetched.body.qty, 5);

  const missing = invokeRoute(router, 'GET', '/inventory/:sku', {
    params: { sku: 'UNKNOWN' },
  });
  assert.strictEqual(missing.status, 404);
})();
