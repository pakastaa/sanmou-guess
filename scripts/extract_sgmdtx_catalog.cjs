/* eslint-disable */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const dir = process.argv[2];
const out = process.argv[3];
const files = fs
  .readdirSync(dir)
  .filter((name) => name.endsWith(".js"))
  .map((name) => path.join(dir, name));

const modules = {};
const sandbox = {
  self: {},
  window: {},
  document: { createElement: () => ({ style: {} }) },
  console,
};
sandbox.window = sandbox;
sandbox.global = sandbox;
sandbox.self.webpackChunk_N_E = [];
sandbox.self.webpackChunk_N_E.push = (payload) => {
  Object.assign(modules, payload[1] || {});
};

const ctx = vm.createContext(sandbox);
for (const file of files) {
  vm.runInContext(fs.readFileSync(file, "utf8"), ctx, { filename: file });
}

const cache = {};
function req(id) {
  const key = Object.prototype.hasOwnProperty.call(modules, id)
    ? id
    : Object.keys(modules).find((item) => Number(item) === Number(id));
  if (!key) throw new Error(`missing module ${id}`);
  if (cache[key]) return cache[key].exports;
  const mod = { exports: {} };
  cache[key] = mod;
  modules[key](mod, mod.exports, req);
  return mod.exports;
}
req.d = (exports, getters) => {
  for (const key of Object.keys(getters)) {
    Object.defineProperty(exports, key, { enumerable: true, get: getters[key] });
  }
};
req.n = (mod) => {
  const getter = mod && mod.__esModule ? () => mod.default : () => mod;
  req.d(getter, { a: getter });
  return getter;
};
req.o = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
req.r = (exports) => {
  Object.defineProperty(exports, "__esModule", { value: true });
};

let catalog = null;
for (const id of Object.keys(modules)) {
  try {
    const exp = req(id);
    const Cls = exp && (exp.ZP || exp.default);
    if (typeof Cls !== "function") continue;
    const inst = new Cls();
    if (inst && typeof inst.getWjs === "function" && typeof inst.getZfs === "function") {
      catalog = { wj: inst.getWjs(), zf: inst.getZfs() };
      break;
    }
  } catch (_err) {
    // Page chunks depend on React modules that are not needed for the data class.
  }
}

if (!catalog) {
  process.stderr.write("catalog class not found\n");
  process.exit(1);
}
fs.writeFileSync(out, JSON.stringify(catalog));
process.stdout.write(
  JSON.stringify({ wj: Object.keys(catalog.wj).length, zf: Object.keys(catalog.zf).length }) + "\n"
);
