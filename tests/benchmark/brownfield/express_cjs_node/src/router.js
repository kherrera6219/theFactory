'use strict';

class InventoryStore {
  constructor() {
    this.bySku = new Map();
  }

  list() {
    return Array.from(this.bySku.values()).map((entry) => Object.assign({}, entry));
  }

  upsert(sku, qty) {
    const cleanSku = String(sku || '').trim();
    const numericQty = Number(qty);
    if (!cleanSku) {
      throw new Error('sku is required');
    }
    if (!Number.isInteger(numericQty) || numericQty < 0) {
      throw new Error('qty must be a non-negative integer');
    }
    const record = { sku: cleanSku, qty: numericQty };
    this.bySku.set(cleanSku, record);
    return Object.assign({}, record);
  }

  get(sku) {
    const record = this.bySku.get(String(sku || '').trim());
    return record ? Object.assign({}, record) : null;
  }
}

function createLightweightRouter() {
  const routes = [];
  return {
    get(path, handler) {
      routes.push({ method: 'GET', path, handler });
    },
    post(path, handler) {
      routes.push({ method: 'POST', path, handler });
    },
    _routes: routes,
  };
}

function createInventoryRouter(store, expressLib) {
  const backing = store || new InventoryStore();
  let router;
  if (expressLib && typeof expressLib.Router === 'function') {
    router = expressLib.Router();
  } else {
    router = createLightweightRouter();
  }

  router.get('/inventory', (req, res) => {
    const items = backing.list();
    return res.status(200).json({ items, total: items.length });
  });

  router.post('/inventory', (req, res) => {
    const body = (req && req.body) || {};
    try {
      const saved = backing.upsert(body.sku, body.qty);
      return res.status(201).json(saved);
    } catch (err) {
      return res.status(400).json({ error: err.message });
    }
  });

  router.get('/inventory/:sku', (req, res) => {
    const sku = req && req.params ? req.params.sku : '';
    const found = backing.get(sku);
    if (!found) {
      return res.status(404).json({ error: 'not found' });
    }
    return res.status(200).json(found);
  });

  return router;
}

module.exports = {
  InventoryStore,
  createInventoryRouter,
};
